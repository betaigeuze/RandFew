import streamlit as st
import pandas as pd
import altair as alt


class DashboardController:
    """Creates all of the visualizations"""

    def __init__(self, dataset: pd.DataFrame, features: list[str]):
        self.dashboard_sidebar = st.sidebar.empty()
        self.dashboard_sidebar.title("Sidebar")
        self.dashboard_sidebar.markdown("# Sidebar")
        self.dashboard = st.container()
        self.dashboard.header("RaFoView")
        self.dataset = dataset
        self.features = features
        self.brush = alt.selection_interval()
        self.range_ = [
            "#8e0152",
            "#c51b7d",
            "#de77ae",
            "#f1b6da",
            "#fde0ef",
            "#f7f7f7",
            "#e6f5d0",
            "#b8e186",
            "#7fbc41",
            "#4d9221",
            "#276419",
        ]
        self.scale_color = alt.Scale(range=self.range_)
        self.color = alt.condition(
            self.brush,
            alt.Color("Silhouette Score:Q", scale=self.scale_color),
            alt.value("black"),
        )

    def create_base_dashboard(self, tree_df: pd.DataFrame):
        self.dashboard.subheader("Tree Data with Feature Importances")
        self.dashboard.write(tree_df)

    def create_feature_importance_barchart(self, tree_df: pd.DataFrame) -> alt.Chart:
        # TODO: COLOR
        chart = (
            alt.Chart(tree_df)
            .transform_fold(self.features, as_=["feature", "importance"])
            .mark_bar()
            .encode(
                x=alt.X("mean(importance):Q"),
                y=alt.Y("feature:N", stack=None, sort="-x"),
            )
            .transform_filter(self.brush)
        )
        return chart

    def basic_scatter(self, tree_df: pd.DataFrame) -> alt.Chart:
        """
        Scatterplot displaying all estimators of the RF model
        """
        # TODO: COLOR
        chart = (
            alt.Chart(tree_df)
            .mark_point()
            .encode(
                x=alt.X("grid_x:N", scale=alt.Scale(zero=False)),
                y=alt.Y("grid_y:N", scale=alt.Scale(zero=False)),
                # color=alt.Color(),
            )
            .add_selection(self.brush)
        )
        return chart

    def create_tsne_scatter(self, tree_df: pd.DataFrame) -> alt.Chart:
        tsne_chart = (
            alt.Chart(tree_df)
            .mark_circle()
            .encode(
                x=alt.X("Component 1:Q", scale=alt.Scale(zero=False)),
                y=alt.Y("Component 2:Q", scale=alt.Scale(zero=False)),
                color=self.color,
                tooltip="cluster:N",
            )
            .add_selection(self.brush)
        )
        silhoutte_chart = self.create_silhouette_plot(tree_df)
        return alt.hconcat(tsne_chart, silhoutte_chart)

    def create_silhouette_plot(self, tree_df: pd.DataFrame) -> alt.Chart:
        # This is not optimal, but apparently there is no way in altair (and not even in)
        # Vega-Lite to sort by 2 attributes at the same time...
        # Let's just hope, we dont need any sorting after this point
        # Note the sort=None, because altair would otherwise overwrite the pandas sort
        tree_df.sort_values(
            by=["cluster", "Silhouette Score"], ascending=False, inplace=True
        )
        chart = (
            alt.Chart(tree_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    "tree:N",
                    sort=None,
                    axis=alt.Axis(labels=False, ticks=False),
                ),
                y=alt.Y("Silhouette Score:Q"),
                color=self.color,
                tooltip="Silhouette Score:Q",
            )
            .facet(
                column=alt.Row("cluster:N", sort="descending", title="Cluster"),
                spacing=0.4,
            )
            .resolve_scale(x="independent")
        )
        # Not pretty at all, but autosizing does not work with faceted charts (yet)
        # see: https://github.com/vega/vega-lite/pull/6672
        chart.spec.width = 20

        return chart

    def create_cluster_comparison_bar_plt(self, tree_df: pd.DataFrame) -> alt.Chart:
        # Likely the prefered way to do this
        # However, combining it with the dropdown from below would be really cool
        # It seems I can only do one of each in one chart:
        # Either dropdown OR aggragation and repeat
        chart = (
            alt.Chart(tree_df)
            .mark_bar()
            .encode(
                x=alt.X("cluster:N", sort="-y"),
                y=alt.Y(alt.repeat("column"), type="quantitative"),
                color=alt.Color("cluster:N", scale=self.scale_color),
            )
            .transform_aggregate(
                mean_virginica_f1_score="mean(virginica_f1-score)",
                mean_versicolor_f1_score="mean(versicolor_f1-score)",
                mean_setosa_f1_score="mean(setosa_f1-score)",
                groupby=["cluster"],
            )
            .repeat(
                column=[
                    "mean_virginica_f1_score",
                    "mean_versicolor_f1_score",
                    "mean_setosa_f1_score",
                ]
            )
        )
        return chart

    def create_cluster_comparison_bar_plt_dropdown(
        self, tree_df: pd.DataFrame
    ) -> alt.Chart:
        # Example for selection based encodings:
        # https://github.com/altair-viz/altair/issues/1617
        # Problem here:
        # Can't get sorting to work
        # Also, not really sure what kind of aggregation is used for calculating the cluster scores
        # Trying to specify the method made me reach the library limits
        # For now: Leave this here as reference

        columns = [
            "virginica_f1-score",
            "versicolor_f1-score",
            "setosa_f1-score",
        ]
        select_box = alt.binding_select(options=columns, name="column")
        sel = alt.selection_single(
            fields=["column"],
            bind=select_box,
            init={"column": "virginica_f1-score"},
        )
        chart = (
            alt.Chart(tree_df)
            .transform_fold(columns, as_=["column", "value"])
            .transform_filter(sel)
            .mark_bar()
            .encode(
                x=alt.X("cluster:N", sort="-y"),
                y=alt.Y("value:Q"),
                color=alt.Color("cluster:N", scale=self.scale_color),
            )
            .add_selection(sel)
        )
        return chart

    def create_basic_rank_scatter(self, tree_df: pd.DataFrame) -> alt.Chart:
        # Omitted for now, adds little value
        chart = (
            alt.Chart(tree_df)
            .mark_circle(size=20)
            .encode(
                x=alt.X("weighted_avg_f1_rank"),
                y=alt.Y("accuracy_rank"),
                color=self.color,
                tooltip="cluster:N",
            )
            .add_selection(self.brush)
        )
        return chart

    def display_charts(self, *charts: list[alt.Chart]):
        """
        Pass any number of altair charts to this function and they will be displayed.
        The order in the provided list is the order in which the charts will be displayed
        on the page. Concatenated charts will be able to be affected by the selection in the
        scatterplot.
        """
        if len(charts) == 1:
            self.dashboard.altair_chart(charts[0], use_container_width=True)
        else:
            self.dashboard.altair_chart(alt.vconcat(*charts), use_container_width=True)

        # Problems might arise from this:
        # Selection over multiple charts requires me to concatenate them - or so I think
        # However, if I concatenate the charts, interactive selections like the dropdown
        # will appear at the bottom of the page instead of next to the relevant chart
