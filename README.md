# SchlageHomeKit

This repo allows you to add any Wi-Fi-enabled Schlage lock to HomeKit, even without it being supported by HomeKit.

> [!WARNING]
> While this accessory works fine for my needs, it may not be stable enough for you.
> Please try it out in a dev environment first and see how it works.

## Table of Contents
<!-- vim-markdown-toc GFM -->

- [Supported Devices](#supported-devices)
- [Security Note](#security-note)
- [Development](#development)
- [Deployment](#deployment)
- [Credits](#credits)

<!-- vim-markdown-toc -->

## Supported Devices

SchlageHomeKit is designed around and confirmed working only on my `BE489WB`. That said, without having tested it on others,
I *assume* it is compatible with any model of Schlage Wi-Fi locks in your account since it seems that they use the same API.

## Security Note

As of April 2025, Schlage still does not seem to support 2FA for their accounts. This is bad, and they need to support it, but
it means that you don't have to opt to disable it just to be able to use this accessory.

That said, it's worth mentioning that by using this accessory, you are placing a lot of trust in a the security of a couple third parties:

- [HAP-python](https://github.com/ikalchev/HAP-python)'s implementation of the HomeKit Automation Protocol
- [pyschlage](https://github.com/dknowles2/pyschlage) library

The underlying API that pyschlage uses is Yonomi, which was [acquired by Schlage's parent company, Allegion in 2021](https://www.allegion.com/corp/en/news/year/2021/Allegion-Acquires-Yonomi.html).

That said, by using this accessory, you are accepting full risk. I am not responsible for your house somehow getting hacked into.


Additionally, I personally created a separate account to which I shared guest access to the lock. I only use this separate account
for API access in attempt to separate the locks' owner account from any potential adverse action placed on your account if Schlage
suddenly decides you're making too many API requests or are operating outside of their terms of service. I recommend you do the same.

## Development

Use the `setup-dev-env.sh` script to create and use a virtual env:

```bash
source ./venv.sh
```

Run the app with your Schlage credentials passed as env vars before python command:

```bash
SCHLAGE_USER=user@example.com SCHLAGE_PASS=super-complex-password python3 main.py
```

Scan the QR code with the Home app and follow the wizard steps to add the bridge to your Home.

## Deployment

A Docker image and Helm chart are currently a work in progress, and information about them will be added here.

## Credits

This project is only possible due to these excellent libraries:

- [dknowles2/pyschlage](https://github.com/dknowles2/pyschlage)
- [ikalchev/HAP-python](https://github.com/ikalchev/HAP-python)

My project essentially just serves as a means to connect those two together, so I did the easy part.


Thanks @dknowles2 and @ikalchev!
