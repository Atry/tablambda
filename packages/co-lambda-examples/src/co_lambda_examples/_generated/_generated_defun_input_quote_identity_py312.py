# Generated, self-contained module: the import header is added at serialization time (see
# co_lambda._defunctionalize.runnable_defun_module); the body is emitted by the DEFUN lambda
# term and content-addressed by compiled dataclass shape.
from co_lambda._defun_runtime import Lambda, Thunk, interned

@interned
class vg_09def6a672b273a1:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_bead7194d6b06f77())

@interned
class vg_1e07d7ce65bab7fe:

    def __call__(self, a):
        return vg_09def6a672b273a1(a)

@interned
class vg_506c8cb63a6f0574:

    def __call__(self, a):
        return a

@interned
class vg_7f406b885e3bad0b:
    cap_0: Lambda

    def __call__(self, a):
        return vg_832d7b0d9361065d(self.cap_0)

@interned
class vg_832d7b0d9361065d:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_f7bb6e14bc0962b5())

@interned
class vg_bead7194d6b06f77:

    def __call__(self, a):
        return vg_7f406b885e3bad0b(a)

@interned
class vg_da2db120da15b7b5:

    def __call__(self, a):
        return vg_1e07d7ce65bab7fe()

@interned
class vg_f7bb6e14bc0962b5:

    def __call__(self, a):
        return vg_506c8cb63a6f0574()
compiled = vg_da2db120da15b7b5()