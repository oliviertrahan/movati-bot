# Movati Booking Project

The goal of this project is to autobook classes on movati. 
The cron scheduler is deployed on modal: https://modal.com/

## Setup - cron scheduler (booking_bot)

`pip install modal-client`
`modal token new`

Then go on the modal website and setup the credentials under `movati-creds`

### Local testing and deployment

`$ cd booking_bot`

For a local run:
Run `modal run bookClasses.py` to do it on CLI

To deploy it:
Run `modal deploy bookClasses.py` to deploy assuming your tokens are setup

## Setup - web schedule interface

Look at the [Nuxt 3 documentation](https://nuxt.com/docs/getting-started/introduction) to learn more.

### Setup

Make sure to install the dependencies:

```bash
# npm
npm install
```

### Development Server

Start the development server on `http://localhost:3000`:

```bash
# npm
npm run dev
```

### Production

Build the application for production:

```bash
# npm
npm run build
```

### Locally preview production build:

```bash
# npm
npm run preview
```

Check out the [deployment documentation](https://nuxt.com/docs/getting-started/deployment) for more information.


## Info

### category values

6994 : "CARDIO & STRENGTH" 
6995 : "STRENGTH"
6996 : "WELLNESS"
6997 : "AQUA"
6998 : "CARDIO"
6999 : "CYCLE"
7000 : "YOGA"
7090 : "GROUP PERSONAL TRAINING"
7640 : "PERSONAL TRAINING"
12850 : "SEMINARS"
13826 : "DANCE"
13827 : "PILATES"
14507 : "LIFEGUARD"
