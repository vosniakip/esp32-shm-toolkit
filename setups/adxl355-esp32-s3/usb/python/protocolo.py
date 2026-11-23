"""CRC-16/CCITT-FALSE e campos do protocolo serial."""
import binascii
from comum import COLUNAS
def campos(line): return dict(x.split('=',1) for x in line.split(',')[1:] if '=' in x)
def decodificar(line):
    a=line.split(',')
    if len(a)!=len(COLUNAS)+2 or a[0]!='D': raise ValueError('Formato D invalido.')
    prefix,crc=line.rsplit(',',1)
    if len(crc)!=4 or binascii.crc_hqx(prefix.encode('ascii'),0xFFFF)!=int(crc,16): raise ValueError('CRC serial incorreto.')
    v=[int(x) for x in a[1:-1]]
    if any(x<0 for x in v[:2]+v[6:]): raise ValueError('Contador negativo.')
    if any(x < -524288 or x > 524287 for x in v[2:5]): raise ValueError('Aceleracao fora dos 20 bits.')
    if not -1<=v[5]<=4095: raise ValueError('Temperatura invalida.')
    return v
