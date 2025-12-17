from music_bot import MusicBot
from logger import configure_logger


def main() -> None:
    configure_logger()
    MusicBot().run()


if __name__ == "__main__":
   main()
