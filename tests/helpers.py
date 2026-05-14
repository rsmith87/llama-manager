from fastapi.testclient import TestClient as FastAPITestClient


def authenticated_client(app):
    created = app.state.auth_store.create_key("test-admin", "admin")
    client = FastAPITestClient(app)
    client.headers.update({"X-Llama-Manager-Key": created["key"]})
    return client
