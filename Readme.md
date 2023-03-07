# Movati Bot

The goal of this bot is to book classes on movati. 
This is deployed on modal: https://modal.com/

## Setup

`pip install modal-client`
`modal token new`

Then go on the modal website and setup the credentials under `movati-creds`

## Local testing and deployment

For a local run:
Run `modal run bookClasses.py` to do it on CLI

To deploy it:
Run `modal deploy bookClasses.py` to deploy assuming your tokens are setup

