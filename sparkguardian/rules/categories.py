"""What kind of problem a rule reports."""
from enum import Enum


class Category(str, Enum):
    RELIABILITY = "reliability"
    COST = "cost"
    CLARITY = "clarity"
    UDF = "udf"
    PERFORMANCE = "performance"
    GOVERNANCE = "governance"
