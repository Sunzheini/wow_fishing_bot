from core.fishing_bot import FishingBot
from support.app_logging import get_logger
from support.window_utils import enable_dpi_awareness

logger = get_logger(__name__)


def main():
    enable_dpi_awareness()
    bot = FishingBot()
    try:
        bot.run()
    finally:
        bot.shutdown()


if __name__ == "__main__":
    main()
