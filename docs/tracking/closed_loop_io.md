# Closed-loop IO tracking

## INPUT
- user_state snapshot (baselines, last outcomes, constraints)
- current multiplier + streak per exercise
- proposed prescription (load/reps/sets/rest)

## FEEDBACK
- actual performance (load/reps/sets)
- difficulty signal (too_easy | easy | ok | hard | too_hard | fail)
- optional notes / context

## OUTPUT
- updated multiplier + streak + last_update
- next prescription delta (load/reps adjustments)
- clamps applied? (yes/no)
