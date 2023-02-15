import numpy as np
from scipy.sparse import csr_matrix

from anndata import AnnData
import pandas as pd
from typing import Optional

from liana.resource import select_resource
from liana.method._pipe_utils._reassemble_complexes import explode_complexes
from liana.method._pipe_utils import prep_check_adata, filter_resource, assert_covered, filter_reassemble_complexes
from liana.utils._utils import _get_props

from liana.method.sp._SpatialMethod import _SpatialMeta
from liana.method.sp._spatial_pipe import _get_ordered_matrix
from liana.method.sp._spatial_utils import _local_to_dataframe, _standardize_matrix, _rename_means
from liana.method.sp._bivariate_funs import _global_spatialdm, _handle_functions, _get_local_scores



class SpatialLR(_SpatialMeta):
    def __init__(self, _method, _complex_cols):
        super().__init__(method_name=_method.method_name,
                         key_cols=_method.key_cols,
                         reference=_method.reference,
                         )

        self._method = _method # TODO change to method_meta
        self._complex_cols = _complex_cols

    def __call__(self,
                 adata: AnnData,
                 function_name: str,
                 proximity_key = 'proximity',
                 resource_name: str = 'consensus',
                 expr_prop: float = 0.05,
                 pvalue_method: str = 'analytical',
                 n_perm: int = 1000,
                 positive_only: bool = True,
                 use_raw: Optional[bool] = True,
                 layer: Optional[str] = None,
                 verbose: Optional[bool] = False,
                 seed: int = 1337,
                 resource: Optional[pd.DataFrame] = None,
                 inplace=True
                 ):
        """
        Parameters
        ----------
        adata
            Annotated data object.
        resource_name
            Name of the resource to be loaded and use for ligand-receptor inference.
        expr_prop
            Minimum expression proportion for the ligands/receptors (and their subunits).
             Set to `0` to return unfiltered results.
        pvalue_method
            Method to obtain P-values: One out of ['permutation', 'analytical'];
            'analytical' by default.
        n_perm
            Number of permutations to be performed if `pvalue_method`=='permutation'
        positive_only
            Whether to calculate p-values only for positive correlations. `True` by default.
        use_raw
            Use raw attribute of adata if present.
        layer
            Layer in anndata.AnnData.layers to use. If None, use anndata.AnnData.X.
        verbose
            Verbosity flag
        seed
            Random seed for reproducibility.
        resource
            Parameter to enable external resources to be passed. Expects a pandas dataframe
            with [`ligand`, `receptor`] columns. None by default. If provided will overrule
            the resource requested via `resource_name`
        inplace
            If true return `DataFrame` with results, else assign to `.uns`.

        Returns
        -------
        If ``inplace = False``, returns:
        - 1) a `DataFrame` with ligand-receptor correlations for the whole slide (global)
        - 2) a `DataFrame` with ligand-receptor Moran's I for each spot
        - 3) a `DataFrame` with ligand-receptor correlations p-values for each spot
        Otherwise, modifies the ``adata`` object with the following keys:
        - :attr:`anndata.AnnData.uns` ``['global_res']`` with `1)`
        - :attr:`anndata.AnnData.obsm` ``['local_r']`` with  `2)`
        - :attr:`anndata.AnnData.obsm` ``['local_pvals']`` with  `3)`

        """
        if pvalue_method not in ['analytical', 'permutation']:
            raise ValueError('pvalue_method must be one of [analytical, permutation]')

        temp = prep_check_adata(adata=adata,
                                use_raw=use_raw,
                                layer=layer,
                                verbose=verbose,
                                groupby=None,
                                min_cells=None,
                                obsm_keys=[proximity_key],
                                )
        
        dist = adata.obsm[proximity_key]
        local_fun = _handle_functions(function_name)
        
         ## TODO move specifics to method instances (repetitive /w _spatial_pipe)
        if local_fun.__name__== "_local_morans":
            norm_factor = dist.shape[0] / dist.sum()
            weight = csr_matrix(norm_factor * dist)
        else:
            weight = dist.A
        

        # select & process resource
        if resource is None:
            resource = select_resource(resource_name.lower())
        resource = explode_complexes(resource)
        resource = filter_resource(resource, adata.var_names)

        # get entities
        entities = np.union1d(np.unique(resource["ligand"]),
                            np.unique(resource["receptor"]))

        # Check overlap between resource and adata  TODO check if this works
        assert_covered(entities, temp.var_names, verbose=verbose)

        # Filter to only include the relevant features
        temp = temp[:, np.intersect1d(entities, temp.var.index)]

        # global_stats
        lr_res = pd.DataFrame({'means': temp.X.mean(axis=0).A.flatten(),
                               'props': _get_props(temp.X)},
                              index=temp.var_names
                              ).reset_index().rename(columns={'index': 'gene'})

        # join global stats to LRs from resource
        lr_res = resource.merge(_rename_means(lr_res, entity='ligand')).merge(
            _rename_means(lr_res, entity='receptor'))

        # get lr_res /w relevant x,y (lig, rec) and filter acc to expr_prop
        lr_res = filter_reassemble_complexes(lr_res=lr_res,
                                            expr_prop=expr_prop,
                                            _key_cols=self.key_cols,
                                            complex_cols=self._complex_cols
                                            )

        # assign the positions of x, y to the adata
        ligand_pos = {entity: np.where(temp.var_names == entity)[0][0] for entity in
                    lr_res['ligand']}
        receptor_pos = {entity: np.where(temp.var_names == entity)[0][0] for entity in
                        lr_res['receptor']}
        
        # convert to spot_n x lr_n matrices
        x_mat = _get_ordered_matrix(mat=temp.X,
                                    pos=ligand_pos,
                                    order=lr_res['ligand'])
        y_mat = _get_ordered_matrix(mat=temp.X,
                                    pos=receptor_pos,
                                    order=lr_res['receptor'])

        # we use the same gene expression matrix for both x and y
        # TODO move this also to function as _get_local_scores
        lr_res['global_r'], lr_res['global_pvals'] = \
            _global_spatialdm(x_mat=_standardize_matrix(x_mat, local=False, axis=1),
                              y_mat=_standardize_matrix(y_mat, local=False, axis=1),
                              weight=weight,
                              seed=seed,
                              n_perm=n_perm,
                              pvalue_method=pvalue_method,
                              positive_only=positive_only
                              )
            
        local_scores, local_pvals = _get_local_scores(x_mat=x_mat.T,
                                                      y_mat=y_mat.T,
                                                      local_fun=local_fun,
                                                      weight=weight,
                                                      seed=seed,
                                                      n_perm=n_perm,
                                                      pvalue_method=pvalue_method,
                                                      positive_only=positive_only,
                                                      )
        
        local_scores = _local_to_dataframe(array=local_scores.T,
                                          idx=temp.obs.index,
                                          columns=lr_res['interaction'])

        local_pvals = _local_to_dataframe(array=local_pvals.T,
                                          idx=temp.obs.index,
                                          columns=lr_res['interaction'])


        if inplace:
            adata.uns['global_res'] = lr_res
            adata.obsm['local_scores'] = local_scores
            adata.obsm['local_pvals'] = local_pvals

        return None if inplace else (lr_res, local_scores, local_pvals)


# initialize instance
_spatial_lr = _SpatialMeta(
    method_name="SpatialDM",
    key_cols=['ligand_complex', 'receptor_complex'],
    reference="Zhuoxuan, L.I., Wang, T., Liu, P. and Huang, Y., 2022. SpatialDM: Rapid "
              "identification of spatially co-expressed ligand-receptor reveals cell-cell "
              "communication patterns. bioRxiv. "
)

spatialdm = SpatialLR(_method=_spatial_lr,
                      _complex_cols=['ligand_means', 'receptor_means'],
                      )


