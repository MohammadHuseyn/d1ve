<img width="1919" height="968" alt="D1ve" src="https://github.com/user-attachments/assets/d9a1a2c9-76a1-4639-a42d-2048352fe53f" />
# What is D1ve?

**D1ve** is a Docker-based React + Flask application that helps you manage your VMess accounts on your server. With D1ve, you can deploy a V2Ray core on your server and create VMess accounts and subscriptions easily.

## What is V2Ray?

[V2Ray](https://www.v2fly.org/) is a platform for building proxies to bypass network restrictions. You can read more about V2Ray and its subscription system in the official documentation.

# How to use D1ve

1. **Install Docker**  
   You will need Docker installed on your device or server. You can follow [Docker’s installation guide](https://docs.docker.com/get-docker/).

2. **Run D1ve**  

   - **Quick Run (fastest)**:  

   ```bash
   docker run --name d1ve -d \
     -e IP=[YOUR_SERVER_IP] \
     -e VMESS_PORT=[YOUR_DESIRED_VMESS_PORT] \
     -e HOST_PORT=[YOUR_DESIRED_HOST_PORT] \
     -e SUBSCRIPTION_URL=[YOUR_DESIRED_SUBSCRIPTION_URL] \
     -p [YOUR_DESIRED_VMESS_PORT]:[YOUR_DESIRED_VMESS_PORT] \
     -p [YOUR_DESIRED_HOST_PORT]:[YOUR_DESIRED_HOST_PORT] \
     mahsein/d1ve:latest
    ```
    - **Using an environment file (more readable):**:  
    ```
    docker run --name d1ve -d --env-file ./d1ve.env \
     -p [VMESS_PORT]:[VMESS_PORT] \
     -p [HOST_PORT]:[HOST_PORT] \
     mahsein/d1ve:latest
    ```
3. **Access D1ve**
Once running, you can manage your application at:
```
http://[IP]:[HOST_PORT]/[SUBSCRIPTION_URL]
```
# Environment Variables
these are the env needed to use D1ve.
## IP
Your server’s IP address
## VMESS_PORT
The port that the V2Ray core will use to receive packets.
## HOST_PORT
The port where the Flask + React UI will run.
## SUBSCRIPTION_URL
The URL path for your subscription (must start with /).

#
