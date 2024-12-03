import socket
import ssl
from wsgiref.util import request_uri

class URL:
    def __init__(self, url) -> None:
        self.scheme, url = url.split("://", 1)

        assert self.scheme in ["http", "https", "file"]

        if self.scheme == "http":
            self.port = 80
        elif self.scheme == "https":
            self.port = 443
        elif self.scheme == "file":
            self.port = None


        if self.scheme in ["http", "https"]:
            if "/" not in url:
                url += "/"
                self.host, url = url.split("/", 1)
                self.path = "/" + url

            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)

        elif self.scheme == "file":
            self.path = url

    def request_url(self):
        s = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP
        )

        s.connect((self.host, self.port))

        if self.scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)
        headers = {
            "Host": self.host,
            "User-Agent": "my-custom-browser",
            "Connection": "close"
        }

        request = f"GET {format(self.path)} HTTP/1.1\r\n"

        for key, value in headers.items():
            request += f"{key}: {value}\r\n"
        request += "\r\n"

        s.send(request.encode("utf8"))

        response = s.makefile('r', encoding='utf8', newline='\r\n')

        statusline = response.readline()

        version, status, explanation = statusline.split(" ", 2)

        response_headers = {}

        while True:
            line = response.readline()
            if line == "\r\n":
                break;
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()

        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        content = response.read()
        s.close()
        return content

    def request(self):
        if self.scheme in ["http", "https"]:
            self.request_url()
        elif self.scheme == "file":
            with open(self.path, "r") as f:
                return f.read()


def show(body):
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            print(c, end="")

def load(url: URL):
    body = url.request()
    show(body)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        load(URL("file:///home/vlad/code/browser-py/browser.py"))
    else:
        load(URL(sys.argv[1]))
