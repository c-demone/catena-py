#*******************************************************
#* Copyright (c) 2020 by Artelys                       *
#* All Rights Reserved                                 *
#*******************************************************

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#  This example demonstrates how to use Knitro to solve the following
#  simple problem with a second order cone constraint.  
#
#  min   x2-1 + x0^2 + x1^2 + (x2+x3)^2
#  s.t.  sqrt(x0^2 + (2*x2)^2)  - 10*x1 <= 0  (c0)
#        x3^2 + 5*x0 <= 100                   (c1)
#	 2*x1 + 3*x2 <= 100                   (c2)   
#        x2 <= 1, x1 >= 1, x3 >= 2
#
#  Note that the first constraint c0 is a second order cone
#  constraint that can be written in the form: ||Ax+b||<=c'x
#  where A = [1, 0, 0, 0 ,  (b is empty).
#             0, 0, 2, 0]
# 
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


from knitro import *

# Create a new Knitro solver instance.
try:
    kc = KN_new ()
except:
    print ("Failed to find a valid license.")

# Initialize Knitro with the problem definition.

# Add the variables and set their bounds.
# Note: unset bounds assumed to be infinite.
KN_add_vars (kc, 4)
KN_set_var_lobnds (kc, xLoBnds = [-KN_INFINITY, 1.0, -KN_INFINITY, 2.0])
KN_set_var_upbnds (kc, 2, 1.0)

# Add the constraints and set their bounds.
KN_add_cons (kc, 3)
KN_set_con_upbnds (kc, cUpBnds = [0.0, 100.0, 100.0])

# Add coefficients for linear constraint c2. 
lconIndexVars = [1,   2]
lconCoefs     = [2.0, 3.0]
KN_add_con_linear_struct (kc, 2, lconIndexVars, lconCoefs)

# Add coefficient for linear term in constraint c1. 
KN_add_con_linear_struct (kc, 1, 0, 5.0)

# Add coefficient for quadratic term in constraint c1.
KN_add_con_quadratic_struct (kc, 1, 3, 3, 1.0)

# Add coefficient for linear term in constraint c0.
KN_add_con_linear_struct (kc, 0, 1, -10.0)

# Add coefficients for L2-norm constraint components in c0.
# Assume the form ||Ax+b||.
dimA = 2    # A = [1, 0, 0, 0; 0, 0, 2, 0] has two rows
indexRowsA = [0, 1]   # corresponding row index of A 
indexVarsA = [0, 2]   # corresponding variable index
coefsA = [1.0, 2.0]
KN_add_con_L2norm (kc, 0, dimA, indexRowsA, indexVarsA, coefsA,
                   None) # there are no constants, b = empty

# Set minimize or maximize (if not set, assumed minimize)
KN_set_obj_goal (kc, KN_OBJGOAL_MINIMIZE)

# Add constant value to the objective.
KN_add_obj_constant (kc, -1.0) 

# Set quadratic objective structure.
# Note: (x2 + x3)^2 = x2^2 + 2*x2*x3 + x3^2
qobjIndexVars1 = [  0,   2,   3,   2,   1]
qobjIndexVars2 = [  0,   2,   3,   3,   1]
qobjCoefs      = [1.0, 1.0, 1.0, 2.0, 1.0]
KN_add_obj_quadratic_struct (kc, qobjIndexVars1, qobjIndexVars2, qobjCoefs)

# Add linear objective term.
KN_add_obj_linear_struct (kc, 2, 1.0)

# Specify the Interior/Direct algorithm for problems with conic constraints.
KN_set_int_param (kc, KN_PARAM_ALGORITHM, KN_ALG_BAR_DIRECT)
# Enable the special barrier tools for second order cone (SOC) constraints.
KN_set_int_param (kc, KN_PARAM_BAR_CONIC_ENABLE, KN_BAR_CONIC_ENABLE_SOC)
# Specify maximum output.
KN_set_int_param (kc, KN_PARAM_OUTLEV, KN_OUTLEV_ALL)
# Specify special barrier update rule.
KN_set_int_param (kc, KN_PARAM_BAR_MURULE, KN_BAR_MURULE_FULLMPC)

# Solve the problem.
#
# Return status codes are defined in "knitro.py" and described
# in the Knitro manual.
nStatus = KN_solve (kc)

print ()
print ("Knitro converged with final status = %d" % nStatus)

# An example of obtaining solution information.
nStatus, objSol, x, lambda_ =  KN_get_solution (kc)
print ("  optimal objective value  = %e" % objSol)
print ("  optimal primal values x  = (%e, %e, %e, %e)" % (x[0], x[1], x[2], x[3]))
print ("  feasibility violation    = %e" % KN_get_abs_feas_error (kc))
print ("  KKT optimality violation = %e" % KN_get_abs_opt_error (kc))

# Delete the Knitro solver instance.
KN_free (kc)
