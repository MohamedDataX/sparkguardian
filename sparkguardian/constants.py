"""Values shared across the package, kept here to avoid import cycles."""
APP_NAME = "SparkGuardian"
APP_VERSION = "0.1.3"
DEFAULT_CONFIG_FILE = ".sparkguardian.toml"
# Exit codes. 1 is the blocking one so a plain `sparkguardian analyze` fails a
# build on CRITICAL findings and merely warns (2) on everything else.
EXIT_SUCCESS = 0
EXIT_CRITICAL = 1
EXIT_WARNINGS = 2
