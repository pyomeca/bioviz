import numpy as np

try:
    import biorbd
except ImportError:
    import biorbd_casadi as biorbd
    import casadi


class InterfacesCollections:
    class BiorbdFunc:
        def __init__(self, model):
            self.m = model
            self.data = None
            if biorbd.currentLinearAlgebraBackend() == 0:
                self._prepare_function_for_eigen()
                self.get_data_func = self._get_data_from_eigen
            elif biorbd.currentLinearAlgebraBackend() == 1:
                self._prepare_function_for_casadi()
                self.get_data_func = self._get_data_from_casadi
            else:
                raise RuntimeError("Unrecognized currentLinearAlgebraBackend")

        def _prepare_function_for_eigen(self):
            pass

        def _prepare_function_for_casadi(self):
            pass

        def _get_data_from_eigen(self, **kwargs):
            raise RuntimeError("BiorbdFunc is an abstract class and _get_data_from_eigen can't be directly called")

        def _get_data_from_casadi(self, **kwargs):
            raise RuntimeError("BiorbdFunc is an abstract class and _get_data_from_casadi can't be directly called")

        def get_data(self, **kwargs):
            self.get_data_func(**kwargs)
            return self.data

    class Markers(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)
            self.data = np.ndarray((3, self.m.nbMarkers(), 1))

        def _prepare_function_for_casadi(self):
            q_sym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.markers = biorbd.to_casadi_func("Markers", self.m.markers, q_sym)

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            if compute_kin:
                markers = self.m.markers(Q, True, True)
            else:
                markers = self.m.markers(Q, True, False)
            for i in range(self.m.nbMarkers()):
                self.data[:, i, 0] = markers[i].to_array()

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            if self.m.nbMarkers():
                self.data[:, :, 0] = np.array(self.markers(Q))

    class Contact(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)
            self.data = np.ndarray((3, self.m.nbContacts(), 1))

        def _prepare_function_for_casadi(self):
            q_sym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.contacts = biorbd.to_casadi_func("Contacts", self.m.constraintsInGlobal, q_sym, True)

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            if compute_kin:
                contacts = self.m.constraintsInGlobal(Q, True)
            else:
                contacts = self.m.constraintsInGlobal(Q, False)
            for i in range(self.m.nbContacts()):
                self.data[:, i, 0] = contacts[i].to_array()

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            if self.m.nbContacts():
                self.data[:, :, 0] = np.array(self.contacts(Q))

    class SoftContacts(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)
            self.data = np.ndarray((3, self.m.nbSoftContacts(), 1))

        def _prepare_function_for_casadi(self):
            q_sym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.soft_contacts = biorbd.to_casadi_func("SoftContacts", self.m.softContacts, q_sym, True)

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            if compute_kin:
                soft_contacts = self.m.softContacts(Q, True)
            else:
                soft_contacts = self.m.softContacts(Q, False)
            for i in range(self.m.nbSoftContacts()):
                self.data[:, i, 0] = soft_contacts[i].to_array()

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            if self.m.nbContacts():
                self.data[:, :, 0] = np.array(self.soft_contacts(Q))

    class CoM(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)
            self.data = np.ones((4, 1, 1))

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.CoM = biorbd.to_casadi_func("CoM", self.m.CoM, Qsym)

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            if compute_kin:
                CoM = self.m.CoM(Q)
            else:
                CoM = self.m.CoM(Q, False)
            for i in range(self.m.nbSegment()):
                self.data[:3, 0, 0] = CoM.to_array()

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            self.data[:3, :, 0] = self.CoM(Q)

    class Gravity(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)
            self.data = np.zeros(3)

        def _get_data_from_eigen(self):
            self.data = self.m.getGravity().to_array()

        def _prepare_function_for_casadi(self):
            self.gravity = biorbd.to_casadi_func("Gravity", self.m.getGravity)

        def _get_data_from_casadi(self):
            self.data = self.gravity()
            for key in self.data.keys():
                self.data = np.array(self.data[key]).reshape(3)

    class CoMbySegment(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)
            self.data = np.ndarray((3, 1, 1))

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.CoMs = biorbd.to_casadi_func("CoMbySegment", self.m.CoMbySegmentInMatrix, Qsym)

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            self.data = []
            if compute_kin:
                allCoM = self.m.CoMbySegment(Q)
            else:
                allCoM = self.m.CoMbySegment(Q, False)
            for com in allCoM:
                self.data.append(np.append(com.to_array(), 1))

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            self.data = []
            for i in range(self.m.nbSegment()):
                self.data.append(np.append(self.CoMs(Q)[:, i], 1))

    class MusclesPointsInGlobal(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.groups = []
            for group_idx in range(self.m.nbMuscleGroups()):
                muscles = []
                for muscle_idx in range(self.m.muscleGroup(group_idx).nbMuscles()):
                    musc = self.m.muscleGroup(group_idx).muscle(muscle_idx)
                    for via in range(len(musc.musclesPointsInGlobal())):
                        muscles.append(
                            casadi.Function(
                                "MusclesPointsInGlobal", [Qsym], [musc.musclesPointsInGlobal(self.m, Qsym)[via].to_mx()]
                            ).expand()
                        )
                self.groups.append(muscles)

        def _get_data_from_eigen(self, Q=None):
            self.data = []
            self.m.updateMuscles(Q, True)
            idx = 0
            for group_idx in range(self.m.nbMuscleGroups()):
                for muscle_idx in range(self.m.muscleGroup(group_idx).nbMuscles()):
                    musc = self.m.muscleGroup(group_idx).muscle(muscle_idx)
                    for k, pts in enumerate(musc.position().musclesPointsInGlobal()):
                        self.data.append(pts.to_array()[:, np.newaxis])
                    idx += 1

        def _get_data_from_casadi(self, Q=None):
            self.data = []
            for g in self.groups:
                for m in g:
                    self.data.append(np.array(m(Q)))

    class LigamentsPointsInGlobal(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.ligaments = []
            for ligament in self.m.ligaments():
                for via in range(len(ligament.pointsInGlobal())):
                    self.ligaments.append(
                        casadi.Function(
                            "pointsInGlobal", [Qsym], [ligament.pointsInGlobal(self.m, Qsym)[via].to_mx()]
                        ).expand()
                    )

        def _get_data_from_eigen(self, Q=None):
            self.data = []
            self.m.updateLigaments(Q, True)
            idx = 0
            for ligament in self.m.ligaments():
                for k, pts in enumerate(ligament.position().pointsInGlobal()):
                    self.data.append(pts.to_array()[:, np.newaxis])
                idx += 1

        def _get_data_from_casadi(self, Q=None):
            self.data = []
            for l in self.ligaments:
                self.data.append(np.array(l(Q)))

    class MeshColor:
        @staticmethod
        def get_color(model):
            if biorbd.currentLinearAlgebraBackend() == 0:
                return [model.segment(i).characteristics().mesh().color().to_array() for i in range(model.nbSegment())]
            elif biorbd.currentLinearAlgebraBackend() == 1:
                color = []
                for i in range(model.nbSegment()):
                    func = biorbd.to_casadi_func("color", model.segment(i).characteristics().mesh().color().to_mx())
                    color.append(np.array(func()["o0"])[:, 0])
                return color
            else:
                raise RuntimeError("Unrecognized currentLinearAlgebraBackend")

    class MeshPointsInMatrix(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.segments = []
            for i in range(self.m.nbSegment()):
                self.segments.append(
                    casadi.Function("MeshPointsInMatrix", [Qsym], [self.m.meshPointsInMatrix(Qsym)[i].to_mx()]).expand()
                )

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            self.data = []
            if compute_kin:
                meshPointsInMatrix = self.m.meshPointsInMatrix(Q)
            else:
                meshPointsInMatrix = self.m.meshPointsInMatrix(Q, False)
            for i in range(self.m.nbSegment()):
                self.data.append(meshPointsInMatrix[i].to_array()[:, :, np.newaxis])

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            self.data = []
            for i in range(self.m.nbSegment()):
                n_vertex = self.m.segment(i).characteristics().mesh().nbVertex()
                vertices = np.ndarray((3, n_vertex, 1))
                vertices[:, :, 0] = self.segments[i](Q)
                self.data.append(vertices)

    class AllGlobalJCS(BiorbdFunc):
        def __init__(self, model):
            super().__init__(model)

        def _prepare_function_for_casadi(self):
            Qsym = casadi.MX.sym("Q", self.m.nbQ(), 1)
            self.jcs = []
            for i in range(self.m.nbSegment()):
                self.jcs.append(casadi.Function("allGlobalJCS", [Qsym], [self.m.allGlobalJCS(Qsym)[i].to_mx()]))

        def _get_data_from_eigen(self, Q=None, compute_kin=True):
            self.data = []
            if compute_kin:
                allJCS = self.m.allGlobalJCS(Q)
            else:
                allJCS = self.m.allGlobalJCS()
            for jcs in allJCS:
                self.data.append(jcs.to_array())

        def _get_data_from_casadi(self, Q=None, compute_kin=True):
            self.data = []
            for i in range(self.m.nbSegment()):
                self.data.append(np.array(self.jcs[i](Q)))
