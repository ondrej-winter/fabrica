#!/usr/bin/env bash
codex debug models \
  | jq -r '
      .models[]
      | select(.visibility == "list")
      | [
          .slug,
          (.context_window | tostring),
          (.max_context_window | tostring)
        ]
      | @tsv
    ' \
  | column -t -s $'\t'
