import socket
import select
import gc

addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
srv = socket.socket()
srv.bind(addr)
srv.listen(10)

poll = select.poll()
poll.register(srv, select.POLLIN)
while True:
    res = poll.poll(50)
    if len(res):
        item, event = res[0]
        if item is srv:
            try:
                cl, addr = srv.accept()
                content = b'Hello world!'
                ct = 'text/plain'
                size = len(content)
                h = b'HTTP/1.0 200 OK\r\nContent-Type:%s\r\nContent-Length:%s\r\nCache-Control:3600\r\n' % (ct, size)
                cl.sendall(h)
                cl.sendall(b'Connection: close\r\n\r\n')
                cl.sendall(content)
            except OSError:
                pass  # ECONNRESET
    else:
        gc.collect()
