import requests
import yaml
import json

class Zenodo:
    """Interact with Zenodo API"""

    def __init__(self, config_path: str):

        # Configuration
        with open(config_path, "r") as file:
            self.config = yaml.safe_load(file)

        # Sandbox URL for now
        self.zenodo_api_url = "https://sandbox.zenodo.org/api/deposit/depositions"
        self.zenodo_token = self.config["zenodo_token"]

        # API call headers
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.zenodo_token}",
        }

    def create_empty_zenodo_deposition(self) -> requests.models.Response:
        """Create an empty deposition (zenodo record).

        Returns:
            requests.models.Response: Zenodo REST API response.
        Raises:
            RuntimeError: When a new deposition does not get created.
        Note:
            The initial zenodo deposition starts empty, i.e., without any JSON content we add no
            metadata in the new deposition.
        """
        response = requests.post(
            url=self.zenodo_api_url,
            headers=self.headers,
            json={},
        )
        if response.status_code != 201:
            raise RuntimeError(response.json()["message"])

        return response

    def get_zenodo_deposition(self, response: requests.models.Response | int):
        """Query the Zenodo API for an existing deposition

        Args:
            requests.models.Response: existing Zenodo REST API response or an int with
            the ID of said deposition.
        Returns:
            requests.models.Response: existing Zenodo REST API response.
        Raises:
            RuntimeError: If information about a deposition could not be retrived from the
            Zenodo REST API.
        """

        if isinstance(response, requests.models.Response):
            # Here we care about the deposition ID
            deposition = response.json()["id"]
        else:
            # Use the ID if we already have it
            deposition = response

        response = requests.get(
            url=f"{self.zenodo_api_url}/{deposition}",
            json={},
            headers=self.headers,
        )

        if response.status_code != 200:
            raise RuntimeError(response.json()["message"])

        return response

    def update_zenodo_deposition(self, response: requests.models.Response | int, metadata: dict):
       """Update an existing deposition with the Zenodo API

       Args:
           requests.models.Response: existing Zenodo REST API response or an int with
           the ID of said deposition.
           dict: metadata that can be used in Zenodo depositions
       Returns:
           response.status_code: existing Zenodo REST API response.
       Raises:
           RuntimeError: If information about a deposition could not be retrived from the
           Zenodo REST API.
       """


       if isinstance(response, requests.models.Response):
            # Here we care about the deposition ID
            deposition = response.json()["id"]
       else:
            # Use the ID if we already have it
            deposition = response

       response = requests.put(
           url = f"{self.zenodo_api_url}/{deposition}",
           headers = self.headers,
           data = json.dumps(metadata)
       )

       if response.status_code != 200:
           raise RuntimeError(response.json()["message"])

       return response





data = {
     'metadata': {
         'title': 'My first upload',
         'upload_type': 'poster',
         'description': 'This is my first upload',
         'creators': [{'name': 'Doe, John',
                       'affiliation': 'Zenodo'}]
     }
 }

z = Zenodo(config_path="../config/config.yaml")

response = z.get_zenodo_deposition(response = 509023)
response_out = z.update_zenodo_deposition(response = 509023, metadata = data)
response.json()
def main():
    z = Zenodo(config_path="../config/config.yaml")
    response = z.get_zenodo_deposition(response = 509023)
    #z.update_zenodo_deposition(response = 509023, metadata = data)


if __name__ == "__main__":
    main()
