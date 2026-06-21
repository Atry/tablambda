# Generated, self-contained module: the import header is added at serialization time (see
# co_lambda._defunctionalize.runnable_defun_module); the body is emitted by the DEFUN lambda
# term and content-addressed by compiled dataclass shape.
from co_lambda._defun_runtime import Lambda, Thunk, interned

@interned
class vg_07eb33b144707f2e:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_77598bdba9a12cd7())

@interned
class vg_0a32e9e0eed3506d:

    def __call__(self, a):
        return vg_1ea4aae9a3c130bc()

@interned
class vg_0b8ac02c03ab0a83:
    cap_0: Lambda

    def __call__(self, a):
        return vg_22e34a6735a9d841(self.cap_0)

@interned
class vg_1ea4aae9a3c130bc:

    def __call__(self, a):
        return vg_07eb33b144707f2e(a)

@interned
class vg_22e34a6735a9d841:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_5e82a4badd71c4a6())

@interned
class vg_5e82a4badd71c4a6:

    def __call__(self, a):
        return vg_90808ac1cd37d6ee()

@interned
class vg_77598bdba9a12cd7:

    def __call__(self, a):
        return vg_0b8ac02c03ab0a83(a)

@interned
class vg_90808ac1cd37d6ee:

    def __call__(self, a):
        return a
compiled = vg_0a32e9e0eed3506d()