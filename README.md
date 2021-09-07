# gitlab-prometheus
Generate prometheus metrics from gitlab issues


# Setup

## Configruation

I use a project that contains a JSON for the for the configuration variables of this project.  The script will pull the latest config for usage from GitLab.  This
is done as there are others that use my script(s) where I work and this makes it easier for them to go in and set those vars instead of having to adjust the container/scripts.

You will want to setup a config.json in a project and define that project ID in the retro.py file.

## Running and testing locally
This app is designed to be in a container and run via GitLab CI/CD.  So the CI/CD for this project builds and stores in the GitLab container repo.  

You can run it through local docker as well you will just need to create a .env file with GL_ACCESS_TOKEN and your personal access token for GitLab.

## Running through GitLab CI/CD
You will need to setup a job to build the container and put it in your container repository.  You will need to also define the GL_ACCESS_TOKEN variable in your variables
