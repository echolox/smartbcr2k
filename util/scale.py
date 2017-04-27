class Scale(object):
    """
    Provides an exponential scale with the provided base to map values in the domain [0, 127] c N
    to the codomain [min, max] c R and back.
    """

    def __init__(self, base, min=0, max=1):
        func = lambda x: ((pow(base, x / 127.) - 1) / float(base - 1)) * (max - min) + min
        self.values = [func(x) for x in range(128)]

    def inverse(self, x: float):
        """
        Returns the inverse scale value for x in [min, max] c R
        :param x: input the the inverse function
        :return: an int within [0, 127] c N
        """
        closest = min(self.values, key=lambda v: abs(x - v))
        return self.values.index(closest)

    def __call__(self, x: int):
        """
        Returns the scale value for x in [0, 127] c N 
        :param x: input to the function
        :return: a float within [min, max] c R
        """
        return self.values[x]