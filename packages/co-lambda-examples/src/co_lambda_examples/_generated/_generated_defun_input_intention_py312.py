# Generated, self-contained module: the import header is added at serialization time (see
# co_lambda._defunctionalize.runnable_defun_module); the body is emitted by the DEFUN lambda
# term and content-addressed by compiled dataclass shape.
from co_lambda._defun_runtime import Lambda, Thunk, interned

@interned
class vg_38cce46e5803397d:

    def __call__(self, a):
        return vg_583f2972559f0264(a)

@interned
class vg_506c8cb63a6f0574:

    def __call__(self, a):
        return a

@interned
class vg_583f2972559f0264:
    cap_0: Lambda

    def __call__(self, a):
        return vg_a13f9dfe32c6bbc1(self.cap_0, a)

@interned
class vg_a13f9dfe32c6bbc1:
    cap_0: Lambda
    cap_1: Lambda

    def __call__(self, a):
        return vg_e3a6a3c49ba8832e(a, self.cap_0, self.cap_1)

@interned
class vg_ba5f9e5ba96605be:

    def __call__(self, a):
        return vg_d96366b64cd26e8a(a)

@interned
class vg_d96366b64cd26e8a:
    cap_0: Lambda

    def __call__(self, a):
        return self.cap_0

@interned
class vg_e3a6a3c49ba8832e:
    cap_0: Lambda
    cap_1: Lambda
    cap_2: Lambda

    def __call__(self, a):
        return Thunk(Thunk(self.cap_0, self.cap_1), self.cap_2)

@interned
class vg_f7bb6e14bc0962b5:

    def __call__(self, a):
        return vg_506c8cb63a6f0574()
compiled = Thunk(Thunk(vg_38cce46e5803397d(), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), vg_f7bb6e14bc0962b5())))))))), Thunk(Thunk(vg_38cce46e5803397d(), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), vg_f7bb6e14bc0962b5())))))))), Thunk(Thunk(vg_38cce46e5803397d(), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), vg_f7bb6e14bc0962b5())))))))), Thunk(Thunk(vg_38cce46e5803397d(), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), vg_f7bb6e14bc0962b5())))))))), Thunk(Thunk(vg_38cce46e5803397d(), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), vg_f7bb6e14bc0962b5())))))))), Thunk(Thunk(vg_38cce46e5803397d(), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), vg_f7bb6e14bc0962b5())))))))), Thunk(Thunk(vg_38cce46e5803397d(), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), vg_f7bb6e14bc0962b5())))))))), Thunk(Thunk(vg_38cce46e5803397d(), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), vg_f7bb6e14bc0962b5())))))))), Thunk(Thunk(vg_38cce46e5803397d(), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_f7bb6e14bc0962b5()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), Thunk(Thunk(vg_38cce46e5803397d(), vg_ba5f9e5ba96605be()), vg_f7bb6e14bc0962b5())))))))), vg_f7bb6e14bc0962b5())))))))))