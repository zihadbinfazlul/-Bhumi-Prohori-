import geopandas as gpd

gdf = gpd.read_file("mirpur_plots.geojson")

# sob plot dekhao
print(gdf[["plot_no", "khatian_no", "owner_name"]])

# plot_no diye khujo
result = gdf[gdf["plot_no"] == "502"]
print(result[["plot_no", "khatian_no", "owner_name"]])