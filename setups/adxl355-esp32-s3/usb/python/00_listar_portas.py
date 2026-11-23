from serial.tools import list_ports
ports=list(list_ports.comports())
for p in ports: print(f'{p.device}: {p.description} | {p.hwid}')
if not ports: print('Nenhuma porta encontrada. Confira cabo USB, driver e alimentacao.')
