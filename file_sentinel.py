#! /bin/env python

import json
import logging
import os
import smtplib
import time
import typing as t
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


class Messenger(t.Protocol):
    def send_log_file_with_message(message: str):
        pass


class EmailMessenger:
    def __init__(
        self,
        log_file_location: Path | str,
        receiver_email: str,
        sender_email: str,
        password: str,
    ):
        self.log_file_location = log_file_location
        self.receiver_email = receiver_email
        self.sender_email = sender_email
        self.password = password

    def send_log_file_with_message(self, message: str):
        msg = MIMEMultipart()
        msg["From"] = self.sender_email
        msg["To"] = self.receiver_email
        msg["Subject"] = "Log File Notification"
        msg.attach(MIMEText(message, "plain"))

        with open(self.log_file_location, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{Path(self.log_file_location).name}"',
            )
            msg.attach(part)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(self.sender_email, self.password)
            server.send_message(msg)


def create_default_config() -> Path:
    working_directory = Path.cwd()
    config_path = working_directory / "config.json"
    config = {
        "directory_of_interest": str(working_directory),
        "check_time_interval": 15,
        "log_file_location": str(working_directory / "monitor.txt"),
        "email_receiver": os.getenv("LOGGER_EMAIL_RECEIVER", "reciever@gmail.com"),
        "email_sender": os.getenv("LOGGER_EMAIL_SENDER", "sender@gmail.com"),
        "email_password": os.getenv("LOGGER_EMAIL_PASSWORD", "default_password"),
    }
    with config_path.open("w") as f:
        json.dump(config, f, indent=4)

    return config_path


def read_config(path_to_config: Path | str = "config.json"):
    try:
        with open(path_to_config, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        logging.info(
            f"config file not found, creating default config file at {path_to_config}"
        )
        path_to_default_config = create_default_config()
        with path_to_default_config.open("r") as f:
            config = json.load(f)
    return config


def get_new_files(root_dir, last_check_time):
    root_path = Path(root_dir)
    new_files = {}

    for file in root_path.rglob("*"):
        if file.is_file():
            creation_time = file.stat().st_ctime
            if creation_time > last_check_time:
                creation_time_human_readable = time.ctime(creation_time)
                new_files[str(file)] = creation_time_human_readable

    return new_files


def monitor(root_dir, time_interval, messenger: Messenger):
    last_check_time = time.time()
    while True:
        time.sleep(time_interval * 60)

        new_files = get_new_files(root_dir, last_check_time)
        if len(new_files) > 0:
            logging.info(
                f"new files check, following files were created: {json.dumps(new_files, indent=4)}"
            )
        else:
            messenger.send_log_file_with_message(
                message=f"No new files were created in the last {time_interval} minutes"
            )
            logging.info("new files check, no new files were created")
        last_check_time = time.time()


def main():
    config = read_config()

    logging.basicConfig(
        level=logging.INFO,
        format="{'time':'%(asctime)s', 'message': '%(message)s'}",
        filename=config["log_file_location"],
        filemode="a",
        force=True,
    )

    logging.info(
        f"read config, running with following parameters: {json.dumps(config, indent=4)}"
    )

    emailer = EmailMessenger(
        log_file_location=config["log_file_location"],
        receiver_email=config["email_receiver"],
        sender_email=config["email_sender"],
        password=config["email_password"],
    )

    monitor(
        root_dir=config["directory_of_interest"],
        time_interval=config["check_time_interval"],
        messenger=emailer,
    )


if __name__ == "__main__":
    main()
