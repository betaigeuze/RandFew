"""
warnings, timeit, datetime, chainmap and numpy are mostly used for utility stuff.
multiprocessing is used for parallelization of the graph edit distance.
sklearn is used for the random forest classifier, the clustering and the
tsne embedding.
pandas is handling the dataframes in the background
networkx is used for the graph edit distance
streamlit is only used in this class for caching and the loading spinner
pygraphviz is used to convert the sklearn tree to pygraph and then networkx
"""
import ast
import multiprocessing as mp
import pickle
import re
import warnings
from collections import ChainMap
from datetime import timedelta
from os.path import exists
from pathlib import Path
from timeit import default_timer as timer

import networkx as nx
import numpy as np
import numpy.typing as npt
import pandas as pd
import pygraphviz as pgv
import streamlit as st
from sklearn import tree
from sklearn.cluster import DBSCAN
from sklearn.ensemble import RandomForestClassifier
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler


class RFmodeller:
    """
    Handles the creation of the random forest model, the clustering and the tsne embedding.
    """

    def __init__(
        self,
        data: pd.DataFrame,
        feature_list: list[str],
        target_column: list[str],
        target_names: list[str],
    ):
        self.data = data
        self.features = feature_list
        self.target_column = target_column
        self.target_names = target_names
        if "data_choice" in st.session_state:
            self.data_choice = st.session_state.data_choice
        else:
            self.data_choice = "Iris"
        self.update_load_history()
        (
            self.model,
            self.X_train,
            self.X_test,
            self.y_train,
            self.y_test,
        ) = self.train_model()
        self.directed_graphs = self.create_dot_trees()
        self.distance_matrix = self.compute_distance_matrix()
        (
            self.clustering,
            self.cluster_df,
        ) = self.calculate_tree_clusters()
        (self.tsne_embedding, self.tsne_df) = self.calculate_tsne_embedding()
        self.sample_silhouette_scores = self.calculate_sample_silhouette_scores()
        self.cluster_silhouette_score = self.calculate_cluster_silhouette_score()
        self.percentage_trees_in_clusters = (
            self.calculate_percentage_trees_in_clusters()
        )

    def train_model(self):
        """
        Standard RF classification model
        """
        x = self.data[self.features]
        y = self.data[self.target_column]
        # Have to run this with the .values on X and y, to avoid passing the series with
        # field names etc.
        x_train, x_test, y_train, y_test = train_test_split(
            x.values, y.values, test_size=0.3, random_state=123
        )
        if "n_estimators" not in st.session_state:
            st.session_state.n_estimators = 100

        if self.data_choice == "Digits":
            max_depth = 5
        else:
            max_depth = 10

        forest_model = RandomForestClassifier(
            n_estimators=st.session_state.n_estimators,
            max_depth=max_depth,
            random_state=123,
            oob_score=True,
            n_jobs=-1,
        )
        forest_model.fit(x_train, y_train.ravel())  # type: ignore
        return forest_model, x_train, x_test, y_train, y_test

    def create_dot_trees(self) -> list[nx.DiGraph]:
        """
        Transform the sklearn estimators of Tree class to nxDiGraphs
        """
        directed_graphs = []
        for estimator in self.model.estimators_:
            pgv_tree_string = tree.export_graphviz(
                estimator, feature_names=self.features
            )
            pgv_digraph = pgv.AGraph(directed=True)
            pgv_digraph = pgv.AGraph(pgv_tree_string)
            nx_digraph = nx.DiGraph()
            nx_digraph = nx.nx_agraph.from_agraph(pgv_digraph)
            directed_graphs.append(nx_digraph)
        return directed_graphs

    def slider_session_state_update(
        self, sliders: list, default_values: dict, selection_changed: bool
    ) -> tuple:
        """
        Retrieves the right values for tSNE and DBSCAN.
        If the data selection changed, default values will be returned and the slides
        will be reset accordingly.
        """
        slider_values = []
        if selection_changed:
            for slider_name in sliders:
                st.session_state[slider_name] = default_values[slider_name]
                slider_values.append(default_values[slider_name])
        else:
            for slider_name in sliders:
                if slider_name in st.session_state:
                    slider_values.append(st.session_state[slider_name])
                else:
                    st.session_state[slider_name] = default_values[slider_name]
                    slider_values.append(default_values[slider_name])
        return tuple(slider_values)

    def calculate_tsne_embedding(
        self,
        learning_rate: float = 73.0,
        perplexity: int = 5,
        early_exaggeration: float = 35.0,
    ):
        """
        Calculate the tsne embedding of the distance matrix.
        Uses the parameters from the sidebar.
        Do not be confused by the "unused" arguments, as they are simply not directly
        adressed, but are used in the for loop below via "locals()[parameter]".
        """
        default_value_dict = {
            "Digits": {
                "learning_rate": 40.0,
                "perplexity": 47,
                "early_exaggeration": 6.0,
            },
            "Iris": {
                "learning_rate": 73.0,
                "perplexity": 5,
                "early_exaggeration": 35.0,
            },
        }
        sliders = ["learning_rate", "perplexity", "early_exaggeration"]
        (
            learning_rate,
            perplexity,
            early_exaggeration,
        ) = self.slider_session_state_update(
            sliders,
            default_value_dict[self.data_choice],
            self.data_selection_changed(),
        )
        if self.model.n_estimators < perplexity:
            perplexity = self.model.n_estimators - 1
        tsne = TSNE(
            n_components=2,
            perplexity=perplexity,
            early_exaggeration=early_exaggeration,
            learning_rate=learning_rate,  # type: ignore
            n_iter=1000,
            random_state=123,
            metric="precomputed",
            init="random",
            verbose=0,
        )
        tsne_embedding = tsne.fit_transform(self.distance_matrix)
        tsne_df = pd.DataFrame(tsne_embedding, columns=["Component 1", "Component 2"])
        return tsne_embedding, tsne_df

    def calculate_tree_clusters(self, eps: float = 0.12, min_samples: int = 2):
        default_value_dict = {
            "Digits": {
                "eps": 0.75,
                "min_samples": 2,
            },
            "Iris": {
                "eps": 0.12,
                "min_samples": 2,
            },
        }
        sliders = ["eps", "min_samples"]
        (eps, min_samples,) = self.slider_session_state_update(
            sliders,  # type: ignore
            default_value_dict[self.data_choice],
            self.data_selection_changed(),
        )

        clustering = DBSCAN(
            eps=eps,
            min_samples=min_samples,
            metric="precomputed",
            n_jobs=-1,
            algorithm="brute",
            p=2,
        ).fit(self.distance_matrix)

        cluster_df = pd.DataFrame(
            {
                "cluster": clustering.labels_,
                "tree": list(range(len(self.directed_graphs))),
            }
        )
        return clustering, cluster_df

    def compute_distance_matrix(self) -> npt.NDArray[np.float64]:
        """
        Calculate the pairwise distance matrix for the directed graphs
        If possible, a pickle file is loaded, otherwise the distance matrix is
        calculated and saved to a pickle file.
        The pickle files for all possible iris and digits datasets are included in the repo.
        If they can be found, the'll be computed.
        After calculating any distance matrix, it is saved to a pickle file.
        We use graph edit distance as the distance metric.
        """
        dashboardv1_absolute = Path(__file__).resolve().parent
        pickle_path = dashboardv1_absolute.joinpath(
            "pickle",
            f"distance_matrix_{self.data_choice}{self.model.n_estimators}.pickle",
        )

        # Check for existing pickle
        if not exists(pickle_path):
            st.spinner()
            start = timer()
            # I used this idea: https://stackoverflow.com/a/56038389/12355337
            # Every process gets a slice of the list of graphs.
            # sklearn's pdist won't work because it needs numeric value inputs.
            with mp.Pool() as pool:
                distance_matrix_rows = pool.map(
                    self.calc_dist_matrix_parallel, self.directed_graphs
                )
            # Transform list of dicts into a single dict.
            distance_matrix_dict = dict(ChainMap(*distance_matrix_rows))
            # Assemble distance matrix based on line indices
            distance_matrix = np.zeros(
                (len(self.directed_graphs), len(self.directed_graphs))
            )
            # Transform the dict into a numpy array matrix
            for i in range(len(distance_matrix_dict)):
                distance_matrix[i] = distance_matrix_dict.get(i)
            # https://stackoverflow.com/questions/16444930/copy-upper-triangle-to-lower-triangle-in-a-python-matrix
            distance_matrix = (
                distance_matrix + distance_matrix.T - np.diag(np.diag(distance_matrix))
            )
            distance_matrix = remove_possible_nans(distance_matrix)
            scaler = MinMaxScaler()
            distance_matrix = scaler.fit_transform(distance_matrix)
            if not self.dist_matr_shape_ok(distance_matrix):
                raise ValueError(
                    "RFModeller: Error after calculating distance matrix. Distance matrix shape is not correct."
                )
            stop = timer()
            print(
                f"Time spent in calculcate_distance_matrix: {timedelta(seconds=stop-start)}"
            )

            # Serialize
            pickle_path.touch(
                exist_ok=True
            )  # will create file, if it exists will do nothing
            with open(pickle_path, "wb") as outfile:
                pickle.dump(distance_matrix, outfile)

        # Deserialization
        with open(pickle_path, "rb") as infile:
            distance_matrix_unpickled = pickle.load(infile)

        return distance_matrix_unpickled

    def calc_dist_matrix_parallel(
        self, process_graph: nx.DiGraph
    ) -> dict[int, npt.NDArray[np.float64]]:
        """
        One directed graph will be sent to this method per process.
        We calculate the distances per row.
        Each row is then collected by the multiprocessing pool, which results in the
        distance matrix.
        """
        row_distances = np.zeros(len(self.directed_graphs))
        dg_index = self.directed_graphs.index(process_graph)
        for i, di_graph in enumerate(self.directed_graphs[dg_index:]):
            if i == 0:
                row_distances[i] = 0
            else:
                row_distances[i + dg_index] = nx.graph_edit_distance(
                    di_graph,
                    process_graph,
                    node_match=self.check_node_label_equality,
                    timeout=0.5,
                    roots=("0", "0"),
                )

        return {dg_index: row_distances}

    def dist_matr_shape_ok(self, distance_matrix: np.ndarray):
        return distance_matrix.shape == (
            len(self.directed_graphs),
            len(self.directed_graphs),
        )

    def check_node_label_equality(self, n1: dict, n2: dict) -> bool:
        """
        This function is used to check if two nodes are equal.
        It is used by the graph edit distance function in order to allow the
        detection of more than just morphological differences.
        """
        n1_label = re.split(r"\\", n1["label"])
        n2_label = re.split(r"\\", n2["label"])
        if len(n1_label) == len(n2_label):
            if len(n1_label) == 3:
                n1_nvalues_string_list = n1_label[len(n1_label) - 1].split(" = ")[1]
                n2_nvalues_string_list = n2_label[len(n2_label) - 1].split(" = ")[1]
                n1_nvalues_true_list = ast.literal_eval(n1_nvalues_string_list)
                n2_nvalues_true_list = ast.literal_eval(n2_nvalues_string_list)
                return np.argmax(n1_nvalues_true_list) == np.argmax(
                    n2_nvalues_true_list
                )
            elif len(n2_label) == 4:
                n1_feature_label = n1_label[0].split(" <= ")[0]
                n2_feature_label = n2_label[0].split(" <= ")[0]
                return n1_feature_label == n2_feature_label
            else:
                raise ValueError()
        else:
            return False

    def calculate_percentage_trees_in_clusters(self) -> int:
        """
        Returns how many percent of trees have been assigned to a cluster.
        """
        if -1 in self.cluster_df["cluster"].values:
            return (
                1
                - self.cluster_df["cluster"].value_counts(normalize=True).to_dict()[-1]
            ) * 100
        else:
            return 100

    def calculate_sample_silhouette_scores(self) -> pd.DataFrame:
        try:
            sample_silhouettes = pd.DataFrame(
                silhouette_samples(
                    X=self.distance_matrix,
                    labels=self.cluster_df["cluster"].values,
                    metric="precomputed",
                ),
                columns=["Silhouette Score"],
            )
        except ValueError:
            sample_silhouettes = pd.DataFrame(
                self.distance_matrix.shape[0] * [-1.0], columns=["Silhouette Score"]
            )
        return sample_silhouettes

    def calculate_cluster_silhouette_score(self):
        no_noise_tree_list = self.cluster_df.loc[self.cluster_df["cluster"] > -1][
            "tree"
        ].to_list()
        no_noise_cluster_df = self.cluster_df.loc[self.cluster_df["cluster"] > -1]
        distance_matrix_rows_filtered = np.take(
            self.distance_matrix, no_noise_tree_list, axis=0
        )
        distance_matrix_no_noise = np.take(
            distance_matrix_rows_filtered, no_noise_tree_list, axis=1
        )
        try:
            cluster_silhouette_score = silhouette_score(
                X=distance_matrix_no_noise,
                labels=no_noise_cluster_df["cluster"],
                metric="precomputed",
                sample_size=None,
            )
        except ValueError:
            cluster_silhouette_score = -1.0
        return cluster_silhouette_score

    def update_load_history(self):
        if "load_history" in st.session_state:
            if "app_mode" in st.session_state:
                st.session_state.load_history.append(
                    [self.data_choice, st.session_state.app_mode]
                )
            else:
                st.session_state.load_history.append([self.data_choice, "Tutorial"])
        else:
            st.session_state["load_history"] = ["Iris", "Tutorial"]

    def data_selection_changed(self) -> bool:
        if "load_history" in st.session_state:
            return (
                self.data_choice
                != st.session_state.load_history[st.session_state.counter - 1][0]
            )
        else:
            st.session_state["load_history"] = ["Iris", "Tutorial"]
            return (
                self.data_choice
                != st.session_state.load_history[st.session_state.counter - 1][0]
            )

    def page_changed(self) -> bool:
        if "load_history" in st.session_state:
            return (
                st.session_state.app_mode
                != st.session_state.load_history[st.session_state.counter][1]
            )
        else:
            st.session_state["load_history"] = ["Iris", "Tutorial"]
            return (
                st.session_state.app_mode
                != st.session_state.load_history[st.session_state.counter][1]
            )


def remove_possible_nans(distance_matrix: np.ndarray) -> np.ndarray:
    """
    Remove possible nans, resulting from timeouts in the nx.graph_edit_distance
    (or so I assume).
    """
    # We currently use an arbitrary measure of twice the maximum distance.
    # This is fine for now, but should be adjusted to something more reasonable.
    nan_count = np.count_nonzero(np.isnan(distance_matrix))
    if nan_count > distance_matrix.shape[0]:
        warnings.warn(
            f"{nan_count} NaNs in distance matrix. Consider adjusting timeout parameter in nx.graph_edit_distance."
        )
    square_max = pow(np.nanmax(distance_matrix), 2)
    distance_matrix = np.nan_to_num(distance_matrix, nan=square_max)
    return distance_matrix
