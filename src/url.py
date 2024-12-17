import socket
import ssl

# Entity replacement for HTML encoding
entities = {
    "&lt;": "<",
    "&gt;": ">",
}


class URL:
    """
    A class to parse and handle URLs with support for HTTP, HTTPS, file, and inline data schemes.
    """

    def __init__(self, url: str) -> None:
        # Initialize URL components
        self.scheme: str = ""
        self.host: str = ""
        self.port: int = 0
        self.path: str = ""
        self.data: str = ""
        self.redirect_counts: int = 0
        self.socket: socket.socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        )  # dummy socket because that dumb pyright doesn't see my try-except blocks
        self.cache = {}

        # Parse the scheme
        if "://" in url:
            self.scheme, url = url.split("://", 1)
        elif "," in url:
            self.scheme, url = url.split(",", 1)
        else:
            raise ValueError("Invalid URL format")

        # Validate the scheme
        assert self.scheme in [
            "http",
            "https",
            "file",
            "data:text/html",
        ], "Unsupported scheme"

        # Set default ports for HTTP/HTTPS
        if self.scheme == "http":
            self.port = 80
        elif self.scheme == "https":
            self.port = 443

        # Parse the host and path for HTTP/HTTPS
        if self.scheme in ["http", "https"]:
            if "/" not in url:
                url += "/"
            self.host, url = url.split("/", 1)
            self.path = "/" + url

            # Handle custom ports
            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)

        # Handle file and inline data schemes
        elif self.scheme == "file":
            self.path = url
        elif self.scheme == "data:text/html":
            self.data = url

    def _create_socket(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(10)  # Set timeout for socket operations
        self.socket.connect((self.host, self.port))

        # Wrap the socket with SSL for HTTPS
        if self.scheme == "https":
            ctx = ssl.create_default_context()
            self.socket = ctx.wrap_socket(self.socket, server_hostname=self.host)

    def _send_request(self, request: str) -> None:
        try:
            # Send the request over the existing socket
            self.socket.send(request.encode("utf8"))
        except (BrokenPipeError, ConnectionResetError):
            # Recreate and reconnect the socket if it's closed or broken
            self._create_socket()
            self.socket.send(request.encode("utf8"))

    def _prepare_request(self) -> str:
        headers = {
            "Host": self.host,
            "User-Agent": "my-custom-browser",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip",
        }
        # Construct the HTTP request
        request = f"GET {self.path} HTTP/1.1\r\n"
        for key, value in headers.items():
            request += f"{key}: {value}\r\n"
        request += "\r\n"
        return request

    def _parse_response_headers(self, response) -> tuple:
        statusline = response.readline().decode("utf-8", errors="replace")
        print(f"Status line: {statusline.strip()}")
        version, status, explanation = statusline.split(" ", 2)

        response_headers = {}
        while True:
            line = response.readline().decode("utf-8", errors="replace")
            if line == "\r\n":
                break
            try:
                header, value = line.split(":", 1)
                response_headers[header.lower()] = value.strip()
            except ValueError:
                print(f"Malformed header line: {line}")

        print(f"Response headers: {response_headers}")
        print(f"Host: {self.host}, Path: {self.path}, Port: {self.port}")
        return status, response_headers

    def _read_response_body(
        self, response, response_headers, content_length: int
    ) -> str:
        """
        Reads the HTTP response body and handles transfer encoding and content length.
        """
        # Check if the response is cached
        cache_key = self.scheme + self.host + self.path
        if cache_key in self.cache:
            return self.cache[cache_key]

        body = b""

        # Handle chunked transfer encoding
        if (
            "transfer-encoding" in response_headers
            and response_headers["transfer-encoding"] == "chunked"
        ):
            print("Chunked transfer encoding detected.")
            body = self._parse_chunked_body(response)
        else:
            # Handle fixed content length
            while len(body) < content_length:
                try:
                    chunk = response.read(
                        content_length - len(body)
                    )  # Read from the file-like object
                    if not chunk:
                        print(
                            f"Warning: Connection closed. Only {len(body)} of {content_length} bytes received."
                        )
                        break
                    body += chunk
                except socket.timeout:
                    print("Warning: Socket timeout while reading response body.")
                    break

        # Handle gzip compression if applicable
        if (
            "content-encoding" in response_headers
            and response_headers["content-encoding"] == "gzip"
        ):
            import gzip

            try:
                body = gzip.decompress(body)
                print("GZIP WORKS")
            except gzip.BadGzipFile:
                print("Error: Failed to decompress gzip response")

        # Cache the decoded body if allowed
        cache_control = response_headers.get("cache-control", "")
        decoded_body = body.decode("utf8", errors="replace")
        if cache_control not in ["no-store", ""]:
            self.cache[cache_key] = decoded_body

        return decoded_body

    def _handle_redirect(self, response_headers) -> str:
        location = response_headers.get("location")
        if not location:
            raise ValueError("Redirect response missing Location header")

        if "://" in location:
            self.scheme, url = location.split("://", 1)
            if "/" not in url:
                url += "/"
            self.host, url = url.split("/", 1)
            self.path = "/" + url
        else:
            self.path = location

        self.redirect_counts += 1
        if self.redirect_counts > 5:
            raise ValueError("Too many redirects")

        return self.request_url()

    def _parse_chunked_body(self, response) -> bytes:
        body = b""
        while True:
            chunked_size_line = response.readline().strip()
            chunk_size = int(chunked_size_line, 16)
            if chunk_size == 0:
                response.readline()
                break
            body += response.read(chunk_size)
            response.readline()
        return body

    def request_url(self) -> str:
        request = self._prepare_request()

        if not self.socket:
            self._create_socket()
        self._send_request(request)

        # Open the response as a binary stream
        response = self.socket.makefile("rb", newline="\r\n")
        statusline, response_headers = self._parse_response_headers(response)

        # Handle body
        if statusline.startswith("2"):  # Status codes 2xx
            if "content-length" in response_headers:
                content_length = int(response_headers["content-length"])
            else:
                content_length = 0  # Default to 0 if not specified
            body = self._read_response_body(response, response_headers, content_length)
            return body
        elif statusline.startswith("3"):  # Status codes 3xx
            return self._handle_redirect(response_headers)
        else:
            raise ValueError(f"Unexpected HTTP status code: {statusline}")

    def request_file(self) -> str:
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
    for i, c in enumerate(body):
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            print(entities.get(body[i : i + 4], c), end="")


def lex(body):
    text = ""
    in_tag = False
    for i, c in enumerate(body):
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            text += entities.get(body[i : i + 4], c)
    return text


def view_source(body):
    for i, c in enumerate(body):
        print(entities.get(body[i : i + 4], c), end="")


def load(url: URL):
    body = url.request()
    show(body)


def load_source(url: URL):
    body = url.request()
    view_source(body)


# if __name__ == "__main__":
#     import sys

#     if len(sys.argv) == 1:
#         load(URL("file:///home/vlad/code/browser-py/browser.py"))
#     else:
#         load_source(URL(sys.argv[1]))
