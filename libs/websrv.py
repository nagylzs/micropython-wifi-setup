import ubinascii
import json
import os

CT_JS = b'application/javascript; charset=UTF-8'

CT = {
    'html': b'text/html; charset=UTF-8',
    'js': CT_JS,
    'json': b'application/json; charset=UTF-8',
    'css': b'text/css; charset=UTF-8',
    'gif': b'image/gif',
    'jpg': b'image/jpeg',
    'png': b'image/png',
    'ico': b'image/x-icon',
    'svg': b'image/svg+xml',
    'ttf': b'font/ttf',
    'eot': b'application/vnd.ms-fontobject',
    'woff': b'font/woff',
    'woff2': b'font/woff2',
    'pdf': b'application/pdf',
}

DEBUG = False


def resp(cl, code, ct, dat):
    h = b'HTTP/1.0 %s\r\nCache-Control:no-cache\r\nContent-Type:%s\r\nContent-Length:%s\r\nConnection: close\r\n\r\n' % (
    code, ct, len(dat))
    if DEBUG:
        print(h.decode('ascii'))
    cl.sendall(h)
    cl.sendall(dat)
    cl.close()


def resp_json(cl, code, data):
    resp(cl, code, CT_JS, json.dumps(data).encode("ascii"))


def error(cl, code):
    resp(cl, code, CT_JS, json.dumps({"code": code}).encode("ascii"))


def serve_get(srv, handle, webroot='/www'):
    cl, addr = srv.accept()
    print("CONNECT!")
    cl_file = cl.makefile('rwb', 0)
    get = None
    while True:
        line = cl_file.readline()
        if not get:
            get = line
            if DEBUG:
                print(line)
        if not line or line == b'\r\n':
            break
    if not get.startswith(b'GET /'):
        error(cl, b"405 Method not allowed")
        return
    sprm = get[5:get.rfind(b' HTTP/')]
    if sprm.startswith(b'api/'):
        params = None
        if sprm:
            try:
                params = json.loads(ubinascii.unhexlify(sprm[4:]))
            except:
                error(cl, b"400 Bad API request")
                return
        try:
            resp_json(cl, b"200 OK", handle(cl, addr, params))
        except Exception as e:
            error(cl, b"500 Internal server error")
            if DEBUG:
                raise
    elif '..' in sprm:
        error(cl, b"403 Unauthorized parent folder")
    else:
        sprm = sprm or b"index.html"
        fp = webroot + "/" + sprm.decode("ascii")
        if DEBUG:
            print("GET /" + fp)
        gz = False
        idx = fp.rfind(".")
        ct = b"text/plain"
        if idx > 0:
            ct = CT.get(fp[idx + 1:], b"text/plain")
        try:
            size = os.stat(fp)[6]
        except OSError:
            fp += ".gz"
            gz = True
            try:
                size = os.stat(fp)[6]
            except OSError:
                error(cl, b"404 Not found")
                return

        h = b'HTTP/1.0 200 OK\r\nContent-Type:%s\r\nContent-Length:%s\r\nCache-Control:3600\r\n' % (ct, size)
        if gz:
            h += b'Content-Encoding:gzip\r\n'
        if DEBUG:
            print(h.decode("ascii"))
        cl.sendall(h)
        cl.sendall(b'Connection: close\r\n\r\n')
        buf = bytearray(512)
        with open(fp, "rb") as fin:
            while True:
                dat = fin.readinto(buf)
                if dat == 0:
                    break
                cl.sendall(buf)
        cl.close()
