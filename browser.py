import socket
import ssl
from typing import Optional

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
        self.host: str= ""
        self.port: int= 0
        self.path: str = ""
        self.data: str = ""
        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # dummy socket because that dumb pyright doesn't see my try-except blocks

        # Parse the scheme
        if "://" in url:
            self.scheme, url = url.split("://", 1)
        elif "," in url:
            self.scheme, url = url.split(",", 1)
        else:
            raise ValueError("Invalid URL format")

        # Validate the scheme
        assert self.scheme in ["http", "https", "file", "data:text/html"], "Unsupported scheme"

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
        """
        Create and initialize a socket for HTTP/HTTPS communication.
        """
        # Create a TCP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(10)  # Set timeout for socket operations
        self.socket.connect((self.host, self.port))

        # Wrap the socket with SSL for HTTPS
        if self.scheme == "https":
            ctx = ssl.create_default_context()
            self.socket = ctx.wrap_socket(self.socket, server_hostname=self.host)

    def _send_request(self, request: str):
        """
        Send an HTTP request over the socket, reconnecting if necessary.
        """
        try:
            # Send the request over the existing socket
            self.socket.send(request.encode("utf8"))
        except (BrokenPipeError, ConnectionResetError):
            # Recreate and reconnect the socket if it's closed or broken
            self._create_socket()
            self.socket.send(request.encode("utf8"))

    def request_url(self):
        """
        Perform an HTTP/HTTPS request and return the response body.
        """
        # Prepare HTTP headers
        headers = {
            "Host": self.host,
            "User-Agent": "my-custom-browser",
            "Connection": "close",  # Persistent connection | change to close for debugging
        }
        # Construct the HTTP request
        request = f"GET {self.path} HTTP/1.1\r\n"
        for key, value in headers.items():
            request += f"{key}: {value}\r\n"
        request += "\r\n"

        # Ensure the socket is created and connected
        if not self.socket:
            self._create_socket()

        # Send the HTTP request
        self._send_request(request)

        # Read the responsOptionale
        response = self.socket.makefile('r', encoding='utf8', newline='\r\n')
        statusline = response.readline()
        version, status, explanation = statusline.split(" ", 2)

        # CHECK HOW THIS WORKs
        # Check for HTTP errors
        if not status.startswith("2"):
            raise ValueError(f"HTTP request failed with status: {status} {explanation.strip()}")


        # Parse headers
        response_headers = {}
        while True:
            line = response.readline()
            if line == "\r\n":
                break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()

        print(f"Response headers: {response_headers}")
        print(f"Host: {self.host}, Path: {self.path}, Port: {self.port}")
        print(f"Request:\n{request}")

        # Handle unsupported features
        assert "transfer-encoding" not in response_headers, "Chunked transfer encoding not supported"
        assert "content-encoding" not in response_headers, "Compressed content not supported"

        # Read response body
        content_length = int(response_headers.get('content-length', 0))
        print(f"Content length: {content_length}\n")
        body = b""
        while len(body) < content_length:
            try:
                chunk = self.socket.recv(content_length - len(body))
                if not chunk:
                    print(f"Warning: Connection closed. Only {len(body)} of {content_length} bytes received.")
                    break
                body += chunk
            except socket.timeout:
                print("Warning: Socket timeout while reading response body.")
                break

        return body.decode("utf8")

    def request_file(self) -> str:
        """
        Load content from a file.
        """
        with open(self.path, "r") as f:
            return f.read()

    def request(self):
        """
        Dispatch the appropriate request based on the scheme.
        """
        if self.scheme in ["http", "https"]:
            return self.request_url()
        elif self.scheme == "file":
            return self.request_file()
        elif self.scheme == "data:text/html":
            return self.data


def show(body):
    """
    Render the body content, skipping HTML tags.
    """
    in_tag = False
    for i, c in enumerate(body):
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            print(entities.get(body[i:i+4], c), end="")


def view_source(body):
    """
    Render the raw source of the body content.
    """
    for i, c in enumerate(body):
        print(entities.get(body[i:i+4], c), end="")


def load(url: URL):
    """
    Load and display the URL content.
    """
    body = url.request()
    show(body)


def load_source(url: URL):
    """
    Load and display the raw source of the URL content.
    """
    body = url.request()
    view_source(body)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        load(URL("file:///home/vlad/code/browser-py/browser.py"))
    else:
        load_source(URL(sys.argv[1]))
