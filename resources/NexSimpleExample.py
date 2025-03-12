
import bpy

# Initialization
# first we need to define our socket variables!
myFloatA:infloat
myFloatB:infloat = 0.123 #you can also assign a default value!
myV:invec
myBoo:inbool = True
sockMatrix:inmat

# do math between types  using '+' '-' '*' '/' '%' '**' '//' symbols,
# or functions. (see the full list in 'NodeBooster > Glossary' panel)
c = (myFloatA + myFloatB)/2
c = nroot(sin(c),cos(123)) // myFloatB

# do comparisons between types using '>' '<' '!=' '==' '<=' '>='
# result will be a socket bool
isequal = myFloatA == myFloatB
islarger = myV > myBoo
# to bitwise operation with symbols '&', or '|' on socket bool
bothtrue = isequal & islarger

# You can evaluate any python types you wish to, and do operations between socket and python types
frame = bpy.context.scene.frame_current
ActiveLov = bpy.context.object.location
c += abs(frame)

# easily access Vector or Matrix componements.
c += (myV.x ** myV.length) + sockMatrix.translation.z
newvec = combine_xyz(c, frame, ActiveLov.x)

# Do Advanced Matrix and Vector operation 
ActiveMat = bpy.context.object.matrix_world
pytuple = (1,2,3)
TransVec = (sockMatrix.inverted @ ActiveMat) @ newvec
TransVec = sockMatrix @ cross(pytuple,TransVec,)
TransVec = sqrt(TransVec) #math operations can also work entry-wise on vectors.
minElement = min(separate_matrix(sockMatrix)) #get lowest socketfloat element of Matrix.

# Some types are also itterable
newvalues = []
for i,component in enumerate(TransVec):
    newval = component + minElement + i
    newvalues.append(newval)
TransVec[:] = newvalues

## Because we are using python you can create functions you can reuse too
def entrywise_sinus_on_matrix_element(SockMatrix):
    new = []
    for f in separate_matrix(SockMatrix):
        new.append(sin(f))
    return combine_matrix(new)

newMat = entrywise_sinus_on_matrix_element(sockMatrix)

# Then we assign the socket to an output
# you can define a strict output type
# or auutomatically define the output scoket with 'outauto'
BoolOut:outbool = bothtrue
TransVec:outvec = TransVec
myMatrix:outauto = newMat