#!/usr/bin/env Rscript
# Pull NFLFastR play-by-play data and write per-season parquet files
# Usage: Rscript scripts/pull_pbp.R [start_season] [end_season]
# Default: 2005 to 2025

library(nflfastR)
library(nflreadr)
library(arrow)

args <- commandArgs(trailingOnly = TRUE)
start_season <- if (length(args) >= 1) as.integer(args[1]) else 2005
end_season   <- if (length(args) >= 2) as.integer(args[2]) else 2025

raw_dir <- "data/raw"
if (!dir.exists(raw_dir)) dir.create(raw_dir, recursive = TRUE)

cat(sprintf("Pulling NFLFastR PBP %d-%d\n", start_season, end_season))

for (season in start_season:end_season) {
  out_path <- file.path(raw_dir, sprintf("pbp_%d.parquet", season))
  if (file.exists(out_path)) {
    cat(sprintf("  Season %d: already cached, skipping\n", season))
    next
  }
  cat(sprintf("  Season %d: downloading...\n", season))
  pbp <- tryCatch(
    load_pbp(seasons = season),
    error = function(e) { cat(sprintf("  ERROR: %s\n", e$message)); NULL }
  )
  if (!is.null(pbp)) {
    write_parquet(pbp, out_path)
    cat(sprintf("  Season %d: written to %s\n", season, out_path))
  }
}

cat("Done.\n")
