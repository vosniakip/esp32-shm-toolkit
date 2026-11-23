"""Captura ADXL355/S3. Preserva parciais e nunca sobrescreve uma aquisicao."""
from __future__ import annotations
import argparse,csv,platform,sys,time
from datetime import datetime,timezone
from pathlib import Path
import serial
from serial.tools import list_ports
from comum import COLUNAS,FORMATO,VERSAO_PACOTE,nome_seguro,nova_pasta,salvar_json,sha256
from protocolo import campos,decodificar

def argumentos():
    p=argparse.ArgumentParser(description='Captura ADXL355 + ESP32-S3 por USB/serial.')
    p.add_argument('--porta'); p.add_argument('--baud',type=int,default=921600)
    p.add_argument('--duracao',type=float,required=True,help='Segundos: 0.1 a 86400')
    p.add_argument('--ensaio',required=True); p.add_argument('--posicao',default='na'); p.add_argument('--repeticao',type=int,default=1)
    p.add_argument('--sensor',default='ADXL355-01'); p.add_argument('--observacao',default='')
    p.add_argument('--montagem',default='',help='Identificador da fixacao fisica, ex.: NO01_M1; mude apos alterar a fixacao.')
    p.add_argument('--referencial',choices=['conjunto','sensor','nao_definido'],default='nao_definido',help='Referencia usada para rotular a posicao; os valores transmitidos continuam brutos.')
    p.add_argument('--saida-raiz',default='dados/brutos'); p.add_argument('--espera-reset',type=float,default=2.5)
    return p.parse_args()
def receber_linha(ser):
    if not hasattr(ser,'_buffer_adxl'): ser._buffer_adxl=bytearray()
    buf=ser._buffer_adxl
    if b'\n' not in buf: buf.extend(ser.read(max(1,min(ser.in_waiting,8192))))
    if len(buf)>65536: raise RuntimeError('Fluxo sem nova linha. Confira firmware/baud.')
    if b'\n' not in buf: return None
    i=buf.index(10); line=bytes(buf[:i]); del buf[:i+1]; return line.decode('ascii',errors='replace').strip()
def executar(args):
    if not .1<=args.duracao<=86400 or args.repeticao<1 or args.espera_reset<0: raise ValueError('Duracao/repeticao/espera invalida.')
    if args.ensaio in ('calibracao_completa','validacao_calibracao') and (not args.montagem.strip() or args.referencial!='conjunto'):
        raise ValueError('Para esta campanha, informe --montagem NO01_M1 --referencial conjunto e oriente pelo gabarito.')
    ports=list(list_ports.comports()) if not args.porta else []
    if not args.porta and len(ports)!=1: raise ValueError('Informe --porta; consulte 00_listar_portas.py.')
    porta=args.porta or ports[0].device
    out=nova_pasta(Path(args.saida_raiz)/datetime.now().strftime('%Y-%m-%d')/nome_seguro(args.ensaio),f'{args.sensor}_{args.posicao}_r{args.repeticao:02d}')
    cp=out/'aquisicao.csv'; jp=out/'aquisicao.json'; lp=out/'aquisicao.log.txt'
    meta=dict(formato=FORMATO,versao_pacote=VERSAO_PACOTE,sensor=args.sensor,montagem=args.montagem.strip(),referencial_posicao=args.referencial,ensaio=args.ensaio,posicao=args.posicao.lower(),repeticao=args.repeticao,observacao=args.observacao,porta=porta,baud=args.baud,
        duracao_s_solicitada=args.duracao,inicio_utc=datetime.now(timezone.utc).isoformat(),configuracao={},fim_firmware={},amostras_recebidas=0,linhas_invalidas=0,captura_completa=False,interrompida=False,erro=None,computador=platform.platform(),python=platform.python_version())
    ser=None; stopped=False; started=False; last_index=-1; last_t=-1
    print(f'Pasta da aquisicao: {out.resolve()}')
    with cp.open('x',newline='',encoding='utf-8') as f, lp.open('x',encoding='utf-8') as log:
        writer=csv.writer(f); writer.writerow(COLUNAS)
        def registrar(line): log.write(f'{datetime.now(timezone.utc).isoformat()} {line}\n'); log.flush()
        def enviar(cmd): registrar('TX '+cmd); ser.write((cmd+'\n').encode('ascii')); ser.flush()
        try:
            ser=serial.Serial(porta,args.baud,timeout=.1,write_timeout=2)
            time.sleep(args.espera_reset); ser.reset_input_buffer(); enviar('INFO'); deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                line=receber_linha(ser)
                if not line: continue
                registrar(line)
                if line.startswith('#INFO,'):
                    info=campos(line)
                    if info.get('formato')!=FORMATO: raise RuntimeError('Firmware de outro pacote. Grave adxl355_aquisicao.ino.')
                    meta['configuracao']=info
                    if info.get('pronto')!='1': raise RuntimeError('Sensor nao pronto: confira 3V/GND, SPI e IDs AD,1D,ED.')
                    break
            else: raise RuntimeError('Sem INFO. Confira COM, USB CDC On Boot, baud e firmware.')
            enviar(f'START,{round(args.duracao*1000)}'); deadline=time.monotonic()+args.duracao+15
            last_rx=last_flush=time.monotonic(); print('Capturando. Ctrl+C encerra e preserva o registro parcial.')
            while time.monotonic()<deadline:
                try: line=receber_linha(ser)
                except KeyboardInterrupt:
                    if stopped: raise
                    meta['interrompida']=True; stopped=True; enviar('STOP'); deadline=time.monotonic()+7; continue
                if not line:
                    if time.monotonic()-last_rx>7: raise RuntimeError('Sem dados por 7 s: confira DRDY14 e USB.')
                    continue
                last_rx=time.monotonic()
                if line.startswith('#'):
                    registrar(line)
                    if line.startswith('#START,'): started=True
                    if line.startswith(('#FATAL','#ERRO')): raise RuntimeError(line)
                    if line.startswith('#END,'): meta['fim_firmware']=campos(line); break
                    continue
                try:
                    v=decodificar(line)
                    if not started: raise ValueError('D antes de START.')
                    if v[0]<=last_index or v[1]<=last_t: raise ValueError('Indice/tempo nao crescente.')
                    last_index,last_t=v[:2]
                except (ValueError,UnicodeError) as exc:
                    meta['linhas_invalidas']+=1; registrar(f'INVALIDA {exc}: {line}'); continue
                writer.writerow(v); meta['amostras_recebidas']+=1
                if time.monotonic()-last_flush>=1: f.flush(); last_flush=time.monotonic()
                if meta['amostras_recebidas']%5000==0: print(f"  {meta['amostras_recebidas']} amostras")
            if not meta['fim_firmware']: raise RuntimeError('Nao foi recebido #END; registro parcial.')
            end=meta['fim_firmware']; n=meta['amostras_recebidas']
            meta['captura_completa']=(not meta['interrompida'] and end.get('motivo')=='tempo_concluido' and n>0 and meta['linhas_invalidas']==0 and int(end.get('enviadas',-1))==n and int(end.get('perdidas',-1))==0 and int(end.get('erros_spi',-1))==0 and last_index+1==n and int(end.get('eventos_drdy',-1))==n)
            if not meta['captura_completa']: meta['erro']='Registro parcial ou com perdas. Consulte log e temporizacao.'
        except KeyboardInterrupt: meta['interrompida']=True; meta['erro']='Captura interrompida.'
        except Exception as exc: meta['erro']=f'{type(exc).__name__}: {exc}'; registrar('FALHA '+meta['erro'])
        finally:
            if ser is not None:
                if not meta['fim_firmware']:
                    try: enviar('STOP')
                    except Exception: pass
                ser.close()
            f.flush(); meta['fim_utc']=datetime.now(timezone.utc).isoformat(); meta['csv_sha256']=sha256(cp)
            sources=Path(__file__).resolve().parents[1]/'firmware/adxl355_aquisicao'
            meta['fontes_locais_sha256']={p.name:sha256(p) for p in sorted(sources.glob('*')) if p.is_file()}
            meta['nota_hash']='Fontes locais; nao comprovam qual binario foi gravado na placa.'; salvar_json(meta,jp)
    print(f'CSV: {cp.resolve()}\nJSON: {jp.resolve()}\nLog: {lp.resolve()}')
    if meta['erro']: print('ERRO: '+meta['erro']); return 1
    print(f"Concluido: {meta['amostras_recebidas']} amostras sem perdas detectadas."); return 0
if __name__=='__main__':
    try: raise SystemExit(executar(argumentos()))
    except (ValueError,OSError) as e: print('ERRO: '+str(e),file=sys.stderr); raise SystemExit(2)
