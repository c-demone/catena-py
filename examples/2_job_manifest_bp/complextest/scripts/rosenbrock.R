# Copyright (C) 2016 Artelys.
#
# Unconstrainted minimization of the Rosenbrock function
#
#   \min_x 100*(x2-x1*x1)^2+(1-x1)^2
#
# x0 = (-1.2, 1)
#

# Load KnitroR package
library('KnitroR')

# Objective function
eval_f <- function(x)
{
    return (100 * (x[2] - x[1] * x[1])^2 + (1 - x[1])^2)
}

# Gradient
eval_grad_f <- function(x)
{
    return (c(2 * x[1] - 2 + 400 * x[1]^3 - 400 * x[1] * x[2],
              200 * (x[2] - x[1]^2)))
}

# Initial guess
x0 <- c(-1.2, 1)

cat("Optimizing with finite differences...\n")
res <- knitro(x0 = x0,
              objective = eval_f)
print(res)

cat("Optimizing with exact gradient gradient...\n")
res <- knitro(x0 = x0,
              objective = eval_f,
              gradient = eval_grad_f)
print(res)
