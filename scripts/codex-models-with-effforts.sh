#!/usr/bin/env bash
codex debug models \
  | jq -r '
      .models[]
      | select(.visibility == "list")
      | . as $model
      | $model.supported_reasoning_levels[]
      | [
          $model.slug,
          (
            if .effort == $model.default_reasoning_level
            then "\(.effort) [default]"
            else .effort
            end
          ),
          .description
        ]
      | @tsv
    ' \
  | column -t -s $'\t'
