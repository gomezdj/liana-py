from __future__ import annotations

from anndata import AnnData
import pandas as pd
from typing import Optional

from liana.method.sp._SpatialBivariate import SpatialBivariate
from liana._constants._docs import d

class SpatialLR(SpatialBivariate):
    """ A child class of SpatialBivariate for ligand-receptor analysis. """
    def __init__(self):
        super().__init__(x_name='ligand', y_name='receptor')

    @d.dedent
    def __call__(self,
                 adata: AnnData,
                 function_name: str,
                 resource_name: str = 'consensus',
                 resource: Optional[pd.DataFrame] = None,
                 interactions=None,
                 expr_prop: float = 0.05,
                 n_perms:(None | int) = None,
                 mask_negatives: bool = False,
                 seed: int = 1337,
                 add_categories: bool = False,
                 use_raw: Optional[bool] = True,
                 layer: Optional[str] = None,
                 connectivity_key = 'spatial_connectivities',
                 inplace=True,
                 key_added='global_res',
                 obsm_added='local_scores',
                 lr_sep='^',
                 verbose: Optional[bool] = False,
                 ):
        """
        Local ligand-receptor interaction metrics and global scores.
        
        Parameters
        ----------
        %(adata)s
        %(function_name)s
        %(resource_name)s
        %(resource)s
        %(interactions)s
        %(expr_prop)s
        %(n_perms)s
        %(mask_negatives)s
        %(seed)s
        %(add_categories)s
        %(use_raw)s
        %(layer)s
        %(connectivity_key)s
        %(inplace)s
        %(key_added)s
        obsm_added: str
            Key in `adata.obsm` where the local scores are stored.
        %(lr_sep)s
        %(verbose)s
        
        Returns
        -------
        Returns `adata` with the following fields, if `inplace=True`:
            - `adata.uns[key_added]` - global results (pd.DataFrame)
            - `adata.obsm[obsm_added]` - local scores (AnnData object)
        if `inplace=False`, returns a the above.
        """
        
        lr_res, local_scores = super().__call__(
            mdata=adata,
            function_name=function_name,
            connectivity_key=connectivity_key,
            resource_name=resource_name,
            resource=resource,
            interactions=interactions,
            nz_threshold=expr_prop,
            n_perms=n_perms,
            mask_negatives=mask_negatives,
            add_categories=add_categories,
            x_mod=True,
            y_mod=True,
            x_use_raw=use_raw,
            x_layer=layer,
            seed=seed,
            verbose=verbose,
            xy_sep=lr_sep,
            inplace=False,
            complex_sep='_'
            )
                     
        return self._handle_return(adata, lr_res, local_scores, key_added, obsm_added, inplace)

lr_bivar = SpatialLR()
