<p class="text-font">
In figure 5 and 6 we go even more in depth on the idea of clusters. On the left side, you can see a <i>t-SNE-embedding</i> of our trees. You can view this as an image of our forest from above while flying over it. What the t-SNE algorithm does, is assigning each of the trees a x- and y-coordinate, also called <i>components</i> to display them on a 2D plane. The depiction supports our results from the DBSCAN cluster algorithm. Many groups of trees that you see in the t-SNE plot, represent a cluster that was previously identified by the DBSCAN algorithm. Another argument supporting our theory is the <i>Silhouette Plot</i> on the right. All of our other clusters have scores well above 0.5, which further indicates a good clustering of the trees. However, do not mistake the Silhouette Score as an absolute measure. It is merely an indication to use as a relative measure, compared to other clusterings of the same data. So if you later proceed to change the parameters of the DBSCAN algorithm, you might find clusterings that are better or worse. That's where the Silhouette Score can help you.  
<br>
Note, that some data points in the t-SNE plot have a Silhouette Score of -1. This is exclusively the case for the points classified as <i>noise</i> by the DBSCAN algorithm. Since this group of noise is not a cluster in the traditional sense, we artificially set their score to -1, as calculating it for these points, would not hold any value. This is because the Silhouette Score is not ideal to be used with an algorithm like DBSCAN that classifies points as noise.
You can also use your mouse to highlight a group of trees in the TSNE plot.