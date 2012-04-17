def test_2d_acoustics():
    """ tests against known classic results """

    def verify_data(data_filename):
        def verify(test_pressure):
            import os
            import numpy as np
            from clawpack.pyclaw.util import check_diff
            """ verifies 2d homogeneous acoustics from a previously verified run """
            thisdir = os.path.dirname(__file__)
            expected_pressure = np.loadtxt(os.path.join(thisdir,data_filename))
            test_err = np.linalg.norm(expected_pressure-test_pressure)
            expected_err = 0
            return check_diff(expected_err, test_err, abstol=1e-4)
        return verify

    from clawpack.pyclaw.util import gen_variants
    from acoustics import acoustics2D

    classic_tests = gen_variants(acoustics2D, verify_data('verify_classic.txt'),
                                 python_kernel=False, solver_type='classic')

    sharp_tests   = gen_variants(acoustics2D, verify_data('verify_sharpclaw.txt'),
                                 python_kernel=False, solver_type='sharpclaw')

    from itertools import chain
    for test in chain(classic_tests, sharp_tests):
        yield test
