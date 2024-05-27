# KuroBot

A discord bot that can ASR and summarize result.

## About The Project

This project is intended to practice and enhance my backend development skills, such as Python, API integration, File Process .  

## Getting Started

You need crate your "Discord-bot", click the link https://discord.com/developers/applications

Get your Discord-bot token and keep it private.
and set environment "DISCORD_API_KEY"
```
DISCORD_API_KEY = "your bot token"
```

You also need crate your "gemini api key", click the link https://aistudio.google.com/app/apikey

Get Google gemini api key and keep it private.
and set environment "GOOGLE_API_KEY"
```
GOOGLE_API_KEY = "your gemini api key"
```

### Prerequisites
Using the ASR feature requires at least 6 GB of VRAM.

### Environment
This project is developed on a old hardware, but these information may still be helpful for you :

| CPU | GPU | VRAM | Python | PyTorch |
|  ----  | ----  | ----  | ----  | ----  |
| 3500X | RTX 2060 | 6GB | 3.9.6 | 2.0.1+cu118|
