# Generated, self-contained module: the import header is added at serialization time (see
# co_lambda._defunctionalize.runnable_defun_module); the body is emitted by the DEFUN lambda
# term and content-addressed by compiled dataclass shape.
from co_lambda._defun_runtime import Lambda, Thunk, interned

@interned
class vg_03a3e8ce27d6a7a2:

    def __call__(self, a):
        return Thunk(Thunk(a, vg_8bef520065e43d58()), vg_77598bdba9a12cd7())

@interned
class vg_0b8ac02c03ab0a83:
    cap_0: Lambda

    def __call__(self, a):
        return vg_22e34a6735a9d841(self.cap_0)

@interned
class vg_0fbc10420ed9f74e:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_8f328f00202cf214())

@interned
class vg_16f2ce6352e69203:

    def __call__(self, a):
        return vg_a3d71a2af140cd9a(a)

@interned
class vg_22e34a6735a9d841:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_5e82a4badd71c4a6())

@interned
class vg_2c3101a5dbfd3cfc:

    def __call__(self, a):
        return vg_b2585d4c358bf6db(a)

@interned
class vg_32560de94d30e40e:

    def __call__(self, a):
        return vg_c31bbba268820671()

@interned
class vg_446941e7b8c6b459:

    def __call__(self, a):
        return vg_c66c9ee7ccd296e2()

@interned
class vg_4795df2250e6debb:
    cap_0: Lambda
    cap_1: Lambda
    cap_2: Lambda

    def __call__(self, a):
        return Thunk(Thunk(self.cap_0, self.cap_1), self.cap_2)

@interned
class vg_4836e5d1788b0894:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_a7e1df87d98df751())

@interned
class vg_5aacfea722357bfa:

    def __call__(self, a):
        return vg_4836e5d1788b0894(a)

@interned
class vg_5e82a4badd71c4a6:

    def __call__(self, a):
        return vg_90808ac1cd37d6ee()

@interned
class vg_64998775ee9abc18:

    def __call__(self, a):
        return vg_03a3e8ce27d6a7a2()

@interned
class vg_6803f287597ad811:

    def __call__(self, a):
        return vg_e49c10fbd8e6f5c7(a)

@interned
class vg_73db4e8df51091fd:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, Thunk(Thunk(vg_847c076d741b143b(), vg_16f2ce6352e69203()), vg_5e82a4badd71c4a6()))

@interned
class vg_77598bdba9a12cd7:

    def __call__(self, a):
        return vg_0b8ac02c03ab0a83(a)

@interned
class vg_828bc3718b480382:

    def __call__(self, a):
        return Thunk(Thunk(a, vg_6803f287597ad811()), vg_77598bdba9a12cd7())

@interned
class vg_847c076d741b143b:

    def __call__(self, a):
        return vg_d1c148f3f965949b(a)

@interned
class vg_8bef520065e43d58:

    def __call__(self, a):
        return vg_e9f9f64fd37a6fe2(a)

@interned
class vg_8f328f00202cf214:

    def __call__(self, a):
        return vg_5aacfea722357bfa()

@interned
class vg_90808ac1cd37d6ee:

    def __call__(self, a):
        return a

@interned
class vg_99c0582d408439cc:

    def __call__(self, a):
        return vg_0fbc10420ed9f74e(a)

@interned
class vg_a1e680ed7c49564c:

    def __call__(self, a):
        return vg_446941e7b8c6b459()

@interned
class vg_a3d71a2af140cd9a:
    cap_0: Lambda

    def __call__(self, a):
        return self.cap_0

@interned
class vg_a7e1df87d98df751:

    def __call__(self, a):
        return vg_2c3101a5dbfd3cfc()

@interned
class vg_b2585d4c358bf6db:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, vg_a1e680ed7c49564c())

@interned
class vg_b9d539fce4cad054:

    def __call__(self, a):
        return vg_99c0582d408439cc()

@interned
class vg_c31bbba268820671:

    def __call__(self, a):
        return vg_828bc3718b480382()

@interned
class vg_c66c9ee7ccd296e2:

    def __call__(self, a):
        return Thunk(Thunk(a, vg_caa3c92043265716()), vg_32560de94d30e40e())

@interned
class vg_caa3c92043265716:

    def __call__(self, a):
        return vg_64998775ee9abc18()

@interned
class vg_d1c148f3f965949b:
    cap_0: Lambda

    def __call__(self, a):
        return vg_f464dfb25f725a2c(self.cap_0, a)

@interned
class vg_e49c10fbd8e6f5c7:
    cap_0: Lambda

    def __call__(self, a):
        return vg_73db4e8df51091fd(self.cap_0)

@interned
class vg_e9f9f64fd37a6fe2:
    cap_0: Lambda

    def __call__(self, a):
        return vg_fa64f5bda83b7608(self.cap_0)

@interned
class vg_f464dfb25f725a2c:
    cap_0: Lambda
    cap_1: Lambda

    def __call__(self, a):
        return vg_4795df2250e6debb(a, self.cap_0, self.cap_1)

@interned
class vg_fa64f5bda83b7608:
    cap_0: Lambda

    def __call__(self, a):
        return Thunk(self.cap_0, Thunk(Thunk(vg_847c076d741b143b(), vg_5e82a4badd71c4a6()), Thunk(Thunk(vg_847c076d741b143b(), vg_16f2ce6352e69203()), vg_5e82a4badd71c4a6())))
compiled = vg_b9d539fce4cad054()