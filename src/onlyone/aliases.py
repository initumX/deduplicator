from onlyone.core.models import BoostMode, DeduplicationMode

BOOST_ALIASES = {
    "size": BoostMode.SAME_SIZE,
    "extension": BoostMode.SAME_SIZE_PLUS_EXT,
    "filename": BoostMode.SAME_SIZE_PLUS_FILENAME,
    "fuzzy-filename": BoostMode.SAME_SIZE_PLUS_FUZZY_FILENAME,
    "fuzzy": BoostMode.SAME_SIZE_PLUS_FUZZY_FILENAME,
}

BOOST_CHOICES = list(BOOST_ALIASES.keys())

BOOST_HELP_TEXT = (
    "Boost mode for initial file grouping:\n"
    "  size       : Compare only files of the same size\n"
    "  extension  : Compare files of the same size and extension\n"
    "  filename   : Compare files of the same size and filename\n"

    "Example    : %(prog)s -i ~/Downloads --boost filename -m 500K -M 10M -x .jpg\n"
)

DEDUP_MODE_ALIASES = {
    "fast": DeduplicationMode.FAST,
    "normal": DeduplicationMode.NORMAL,
    "full": DeduplicationMode.FULL,
}

DEDUP_MODE_CHOICES = list(DEDUP_MODE_ALIASES.keys())

DEDUP_MODE_HELP_TEXT = (
    "Deduplication mode (depth of analysis):\n"
    "  fast               : Size → Front Hash (fastest, may miss some duplicates)\n"
    "  normal             : Size → Front → Middle → End Hash (balanced)\n"
    "  full               : Size → Front → Middle → Full Hash\n"
    "Example:\n"
    "  %(prog)s -i ~/Downloads --mode fast -m 500K -M 10M"
)

EPILOG_TEXT = """
Examples:
  Basic usage - find duplicates in Downloads folder
  %(prog)s -i ~/Downloads

  Filter files by size and extensions and find duplicates
  %(prog)s -i ~/Downloads -m 500KB -M 10MB -x .jpg,.png
  
  Same as above + move duplicates to trash (with confirmation prompt)
  %(prog)s -i ~/Downloads -m 500KB -M 10MB -x .jpg,.png --keep-one

  Same as above but without confirmation and with output to a file (for scripts)
  %(prog)s -i ~/Downloads -m 500KB -M 10MB -x .jpg,.png --keep-one --force > ~/Downloads/report.txt
  
  Filter files by size, compare only files of the same filename
  %(prog)s -i ~/Downloads/ -m 1K -M 15M --boost filename
  
  For more information check official OnlyOne github page
"""
