import socket
import ssl

entities = {
    "&lt;": "<",
    "&gt;": ">",
}

class URL:
    def __init__(self, url) -> None:
        self.scheme = None
        self.host = None
        self.port = None
        self.path = ""
        self.data = ""

        if "://" in url:
            self.scheme, url = url.split("://", 1)
        elif "," in url:
            self.scheme, url = url.split(",", 1)

        assert self.scheme in ["http", "https", "file", "data:text/html"]

        if self.scheme == "http":
            self.port = 80
        elif self.scheme == "https":
            self.port = 443


        if self.scheme in ["http", "https"]:
            self.host = "" # I get warning from pyright if i dont do this _|_
            if "/" not in url:
                url += "/"
                self.host, url = url.split("/", 1)
                self.path = "/" + url

            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)
        elif self.scheme == "file":
            self.path = url
        elif self.scheme == "data:text/html":
            self.data = url


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

    def request_file(self):
        with open(self.path, "r") as f:
            return f.read()

    def request(self):
        if self.scheme in ["http", "https"]:
            return self.request_url()
        elif self.scheme == "file":
            return self.request_file()
        elif self.scheme == "data:text/html":
            return self.data



def show(body):
    in_tag = False
    i = 0

    while i < len(body):
        c = body[i]

        # Checking for entities
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            if body[i:i+4] == "&lt;":
                print("<", end="")
                i += 3
            elif body[i:i+4] == "&gt;":
                print(">", end="")
                i += 3
            else:
                print(c, end="")
        i += 1

def view_source(body):
    i = 0

    while i < len(body):
        if body[i:i+4] == "&lt;":
            print("<", end="")
            i += 3
        elif body[i:i+4] == "&gt;":
            print(">", end="")
            i += 3
        else:
            print(body[i], end="")
        i += 1


def load(url: URL):
    body = url.request()
    show(body)

def load_source(url: URL):
    body = url.request()
    view_source(body)

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        load(URL("file:///home/vlad/code/browser-py/browser.py"))
    else:
        load_source(URL(sys.argv[1]))
