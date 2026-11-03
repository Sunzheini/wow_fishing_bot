from core.fishing_bot import FishingBot
from support.app_logging import get_logger

logger = get_logger(__name__)


def main():
    bot = FishingBot()
    try:
        bot.run()
    finally:
        bot.shutdown()


if __name__ == "__main__":
    main()
