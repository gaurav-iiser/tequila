from openfermion import QubitOperator
from openvqe.tools import number_to_string

class PauliString:

    """
    Convenient DataClass for single PauliStrings
    Internal Storage is a dictionary where keys are particle-numbers and values the primitive paulis
    i.e. X(1)Y(2)Z(5) is {1:'x', 2:'y', 5:'z'}
    additional a coefficient can be stored
    iteration is then over the dimension
    """

    def key_openfermion(self):
        """
        Convert into key to store in Hamiltonian
        Same key syntax than openfermion
        :return: The key for the openfermion dataformat
        """
        key = []
        for k, v in self._data.items():
            key.append((k, v))
        return tuple(key)

    def __repr__(self):
        result = number_to_string(self.coeff)
        for k, v in self._data.items():
            result += str(v) + "(" + str(k) + ")"
        return result

    def __init__(self, data=None, coeff=None):
        if data is None:
            self._data = {}
        else:
            # stores the paulistring as dictionary
            # keys are the dimensions
            # values are x,y,z
            self._data = data
        self._coeff = coeff

    def items(self):
        return self._data.items()

    @classmethod
    def init_from_openfermion(cls, key, coeff=None):
        data = {}
        for term in key:
            index = term[0]
            pauli = term[1]
            data[index] = pauli
        return PauliString(data=data, coeff=coeff)

    @property
    def coeff(self):
        if self._coeff is None:
            return 1
        else:
            return self._coeff

    @coeff.setter
    def coeff(self, other):
        self._coeff = other
        return self

    def __eq__(self, other):
        return self._data == other._data


class QubitHamiltonian:
    """
    Default Hamiltonian to play around with
    Uses OpenFermion Structure
    Has no special features
    """

    axis_to_string = {0: "x", 1: "y", 2: "z"}
    string_to_axis = {"x": 0, "y": 1, "z": 2}

    @property
    def hamiltonian(self) -> QubitOperator:
        return self._hamiltonian

    @hamiltonian.setter
    def hamiltonian(self, other: QubitOperator) -> QubitOperator:
        self._hamiltonian = other

    def index(self, ituple):
        return ituple[0]

    def pauli(selfs, ituple):
        return ituple[1]

    def __init__(self, hamiltonian: QubitOperator = None):
        if isinstance(hamiltonian, str):
            self._hamiltonian = self.init_from_string(string=hamiltonian)._hamiltonian
        elif hamiltonian is None:
            self._hamiltonian = QubitOperator.identity()
        else:
            self._hamiltonian = hamiltonian

        assert (isinstance(self._hamiltonian, QubitOperator))

    def __repr__(self):
        result = ""
        for ps in self.paulistrings:
            result += str(ps)
        return result

    def __getitem__(self, item):
        return self._hamiltonian.terms[item]

    def items(self):
        return self._hamiltonian.terms.items()

    def keys(self):
        return self._hamiltonian.terms.keys()

    def values(self):
        return self._hamiltonian.terms.values()

    @classmethod
    def init_zero(cls):
        return QubitHamiltonian(hamiltonian=QubitOperator("", 0.0))

    @classmethod
    def init_unit(cls):
        return QubitHamiltonian(hamiltonian=QubitOperator.identity())

    @classmethod
    def init_from_string(cls, string):
        return QubitHamiltonian(hamiltonian=QubitOperator(string.upper(), 1.0))

    @classmethod
    def init_from_paulistring(cls, ps: PauliString):
        return QubitHamiltonian(hamiltonian=QubitOperator(term=ps.key_openfermion(), coefficient=ps.coeff))

    def __add__(self, other):
        return QubitHamiltonian(hamiltonian=self.hamiltonian + other.hamiltonian)

    def __sub__(self, other):
        return QubitHamiltonian(hamiltonian=self.hamiltonian - other.hamiltonian)

    def __iadd__(self, other):
        self.hamiltonian += other.hamiltonian
        return self

    def __isub__(self, other):
        self.hamiltonian -= other.hamiltonian
        return self

    def __mul__(self, other):
        return QubitHamiltonian(hamiltonian=self.hamiltonian * other.hamiltonian)

    def __imul__(self, other):
        self.hamiltonian *= other.hamiltonian
        return self

    def __rmul__(self, other):
        return QubitHamiltonian(hamiltonian=self.hamiltonian * other)

    def __pow__(self, power):
        return QubitHamiltonian(hamiltonian=self.hamiltonian ** power)

    def __eq__(self, other):
        return self._hamiltonian == other._hamiltonian

    def is_hermitian(self):
        for v in self.values():
            if v.imag != 0.0:
                return False
        return True

    def is_antihermitian(self):
        for v in self.values():
            if v.real != 0.0:
                return False
        return True

    def conjugate(self):
        conj_hamiltonian = QubitOperator("", 0)
        for key, value in self._hamiltonian.terms.items():
            sign = 1
            for term in key:
                p = self.pauli(term)
                if p.lower() == "y":
                    sign *= -1
            conj_hamiltonian.terms[key] = sign * value.conjugate()

        return QubitHamiltonian(hamiltonian=conj_hamiltonian)

    def transpose(self):
        trans_hamiltonian = QubitOperator("", 0)
        for key, value in self._hamiltonian.terms.items():
            sign = 1
            for term in key:
                p = self.pauli(term)
                if p.lower() == "y":
                    sign *= -1
            trans_hamiltonian.terms[key] = sign * value

        return QubitHamiltonian(hamiltonian=trans_hamiltonian)

    def dagger(self):
        dag_hamiltonian = QubitOperator("", 0)
        for key, value in self._hamiltonian.terms.items():
            dag_hamiltonian.terms[key] = value.conjugate()

        return QubitHamiltonian(hamiltonian=dag_hamiltonian)

    def normalize(self):
        self._hamiltonian.renormalize()

    @property
    def n_qubits(self):
        n_qubits = 0
        for key, value in self.items():
            indices = [self.index(k) for k in key]
            n_qubits = max(n_qubits, max(indices))
        return n_qubits + 1

    @property
    def paulistrings(self):
        """
        :return: the Hamiltonian as list of PauliStrings
        """
        return [PauliString.init_from_openfermion(key=k, coeff=v) for k, v in self.items()]

    @paulistrings.setter
    def paulistrings(self, other):
        """
        Reassign with OpenVQE PauliString format
        :param other: list of PauliStrings
        :return: self for chaining
        """
        new_hamiltonian = QubitOperator.identity()
        for ps in other:
            tmp = QubitOperator(term=ps.key_openfermion(), value=ps.coeff)
            new_hamiltonian += tmp
        self._hamiltonian = new_hamiltonian
        return self