from starlette.datastructures import Headers
from starlette.requests import Request


class Network:
    @staticmethod
    def get_headers(headers: Headers) -> dict[str, str]:
        custom_header = {
            "Content-Type": "application/json"
        }

        if "Authorization" in headers:
            custom_header["Authorization"] = headers["Authorization"]

        return custom_header

    async def send_get(self, request: Request, url: str):
        requests_client = request.app.requests_client
        headers = self.get_headers(request.headers)

        response = await requests_client.get(
            url,
            headers=headers,
        )

        return response.json()

    async def send_post(self, request: Request, url: str, sync_data: str):
        requests_client = request.app.requests_client
        headers = self.get_headers(request.headers)

        response = await requests_client.post(
            url,
            data=sync_data,
            headers=headers,
        )

        return response.json()
