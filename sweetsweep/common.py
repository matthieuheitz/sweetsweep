# Functions that are common to the sweeper, and the sweep viewer

# Display format for parameter values
def val2str(v):
    return str(v) if isinstance(v,(str,bool)) else "%0.4g"%v
