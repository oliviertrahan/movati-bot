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


## Info

### category values

6994 : "CARDIO & STRENGTH"
6995: "STRENGTH"
6996: "WELLNESS"
6997: "AQUA"
6998: "CARDIO"
6999: "CYCLE"
7000: "YOGA"
7090: "GROUP PERSONAL TRAINING"
7640: "PERSONAL TRAINING"