# ODR Stop Logic (v1)

Priority order:
1. `CODE_LEAK`
2. `MAX_ROUNDS`
3. `DIFF_FLOOR`
4. `CIRCULARITY`

Rules:
1. `CODE_LEAK` checks architect+auditor raw text before parsing.
2. `SHAPE_VIOLATION` is emitted when parse contracts fail.
3. `MAX_ROUNDS` wins over metric triggers when `n == max_rounds`.
4. `DIFF_FLOOR` uses strict `<` comparison.
5. `CIRCULARITY` uses strict `>` margin comparison.
