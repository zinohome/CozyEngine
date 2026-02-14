from locust import HttpUser, task, between
import json

class CozyUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def chat_completion_non_stream(self):
        payload = {
            "model": "perf_test",
            "messages": [{"role": "user", "content": "Hello, are you fast?"}],
            "stream": False,
            "temperature": 0.7
        }
        headers = {
            "x-user-id": "perf-test-user",
            "x-session-id": "perf-test-session",
            "content-type": "application/json"
        }
        with self.client.post("/api/v1/chat/completions", json=payload, headers=headers, catch_response=True, name="/api/v1/chat/completions (non-stream)") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with {response.status_code}: {response.text}")

    @task(1)
    def list_personalities(self):
        with self.client.get("/api/v1/personalities", catch_response=True, name="/api/v1/personalities") as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404: # Maybe M1-1 implemented it differently, checking robustness
                 response.failure("Personalities endpoint not found")
            else:
                response.failure(f"Failed with {response.status_code}")

    @task(1)
    def health_check(self):
        self.client.get("/api/v1/health", name="/api/v1/health")
