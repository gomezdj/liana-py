from liana.steady.Method import Method, MethodMeta
from .cellphonedb import _simple_mean


def _connectome_score(x) -> tuple:
    """
    Calculate Connectome-like Score

    Parameters
    ----------
    x
        DataFrame row

    Returns
    -------
    tuple(expr_prod, scaled_weight)

    """
    # magnitude
    expr_prod = x.ligand_means * x.receptor_means
    # specificity
    scaled_weight = _simple_mean(x.ligand_zscores, x.receptor_zscores)
    return expr_prod, scaled_weight


# Initialize CPDB Meta
_connectome = MethodMeta(method_name="Connectome",
                         complex_cols=['ligand_zscores', 'receptor_zscores',
                                       'ligand_means', 'receptor_means'],
                         add_cols=[],
                         fun=_connectome_score,
                         magnitude='expr_prod',
                         magnitude_desc=True,
                         specificity='scaled_weight',
                         specificity_desc=True,
                         permute=False,
                         reference=''
                         )

# Initialize callable Method instance
connectome = Method(_SCORE=_connectome)
