"""
Interface to get
Quantum Chemistry Hamiltonians for OpenVQE
Derived class of HamiltonianBase: Overwrites the get_hamiltonian function
"""
from openvqe import OutputLevel
from openvqe.openvqe_abc import OpenVQEParameters, parametrized
from openvqe.ansatz import ManyBodyAmplitudes
from dataclasses import dataclass
from openfermion import InteractionOperator, MolecularData
from openfermionpsi4._psi4_conversion_functions import parse_psi4_ccsd_amplitudes
from openfermionpsi4 import run_psi4
from .hamiltonian_base import HamiltonianBase, ParametersHamiltonian
from numpy import float64

@dataclass
class ParametersPsi4(OpenVQEParameters):
    run_scf: bool = True
    run_mp2: bool = False
    run_cisd: bool = False
    run_ccsd: bool = False
    run_fci: bool = False
    verbose: bool = False
    tolerate_error: bool = False
    delete_input: bool = False
    delete_output: bool = False
    memory: int = 8000


@dataclass
class ParametersQC(ParametersHamiltonian):
    """
    Specialization of ParametersHamiltonian
    Parameters for the HamiltonianQC class
    """
    psi4: ParametersPsi4 = ParametersPsi4()
    basis_set: str = ''  # Quantum chemistry basis set
    geometry: str = ''  # geometry of the underlying molecule (units: Angstrom!), this can be a filename leading to an .xyz file or the geometry given as a string
    filename: str = ''
    description: str = ''
    multiplicity: int = 1
    charge: int = 0

    @staticmethod
    def format_element_name(string):
        """
        OpenFermion uses case sensitive hash tables for chemical elements
        I.e. you need to name Lithium: 'Li' and 'li' or 'LI' will not work
        this conenience function does the naming
        :return: first letter converted to upper rest to lower
        """
        assert (len(string) > 0)
        assert (isinstance(string, str))
        fstring = string[0].upper() + string[1:].lower()
        return fstring

    @staticmethod
    def convert_to_list(geometry):
        """
        Convert a molecular structure given as a string into a list suitable for openfermion
        :param geometry: a string specifing a mol. structure. E.g. geometry="h 0.0 0.0 0.0\n h 0.0 0.0 1.0"
        :return: A list with the correct format for openferion E.g return [ ['h',[0.0,0.0,0.0], [..]]
        """
        result = []
        for line in geometry.split('\n'):
            words = line.split()
            if len(words) != 4:  break
            try:
                tmp = (ParametersQC.format_element_name(words[0]),
                       (float64(words[1]), float64(words[2]), float64(words[3])))
                result.append(tmp)
            except ValueError:
                print("get_geometry list unknown line:\n ", line, "\n proceed with caution!")
        return result

    def get_geometry(self):
        """
        Returns the geometry
        If a xyz filename was given the file is read out
        otherwise it is assumed that the geometry was given as string
        which is then reformated as a list usable as input for openfermion
        :return: geometry as list
        e.g. [(h,(0.0,0.0,0.35)),(h,(0.0,0.0,-0.35))]
        Units: Angstrom!
        """
        if self.geometry.split('.')[-1] == 'xyz':
            geomstring, comment = self.read_xyz_from_file(self.geometry)
            self.description = comment
            return self.convert_to_list(geomstring)
        elif self.geometry is not None:
            return self.convert_to_list(self.geometry)
        else:
            raise Exception("Parameters.qc.geometry is None")

    @staticmethod
    def read_xyz_from_file(filename):
        """
        Read XYZ filetype for molecular structures
        https://en.wikipedia.org/wiki/XYZ_file_format
        Units: Angstrom!
        :param filename:
        :return:
        """
        with open(filename, 'r') as file:
            content = file.readlines()
            natoms = int(content[0])
            comment = str(content[1])
            coord = ''
            for i in range(natoms):
                coord += content[2 + i]
            return coord, comment


@parametrized(parameter_class=ParametersQC)
class HamiltonianQC(HamiltonianBase):

    def __post_init__(self, molecule=None):
        """
        Constructor will run psi4 and create the molecule which is stored as member variable
        :param parameters: instance of ParametersQC which holds all necessary parameters
        """
        self.molecule = molecule

    def n_electrons(self):
        """
        Convenience function
        :return: The total number of electrons
        """
        return self.molecule.n_electrons

    def n_orbitals(self):
        """
        Convenience function
        :return: The total number of (spatial) orbitals (occupied and virtual)
        """
        return self.molecule.n_orbitals

    def n_qubits(self):
        """
        Convenience function
        :return: Number of qubits needed
        """
        return 2 * self.n_orbitals()

    def get_fermionic_hamiltonian(self) -> InteractionOperator:
        """
        Note that the Qubit Hamiltonian can be created over the call method which is already implemented in the baseclass
        :return: The fermionic Hamiltonian as InteractionOperator structure
        """
        # fast return if possible
        if self.molecule is None:
            self.molecule = self.make_molecule(self.parameters)
        return self.molecule.get_molecular_hamiltonian()

    @staticmethod
    def make_molecule(parameters: ParametersQC) -> MolecularData:
        """
        Creates a molecule in openfermion format by running psi4 and extracting the data
        Will check for previous outputfiles before running
        :param parameters: An instance of ParametersQC, which also holds an instance of ParametersPsi4 via parameters.psi4
        The molecule will be saved in parameters.filename, if this file exists before the call the molecule will be imported from the file
        :return: the molecule in openfermion.MolecularData format
        """
        print("geom=", parameters.get_geometry())
        print("description=", parameters.description)
        print(parameters)
        molecule = MolecularData(geometry=parameters.get_geometry(),
                                 basis=parameters.basis_set,
                                 multiplicity=parameters.multiplicity,
                                 charge=parameters.charge,
                                 description=parameters.description.strip('\n'),  # '\n' causes openfermion to chrash
                                 filename=parameters.filename)

        # try to load
        do_compute = True
        if parameters.filename:
            try:
                import os
                if os.path.exists(parameters.filename):
                    molecule.load()
                    do_compute = False
            except OSError:
                print("loading molecule from file=", parameters.filename, " failed. Try to recompute")
                do_compute = True

        if do_compute:
            molecule = run_psi4(molecule, run_scf=parameters.psi4.run_scf,
                                run_mp2=parameters.psi4.run_mp2,
                                run_ccsd=parameters.psi4.run_ccsd,
                                run_cisd=parameters.psi4.run_cisd,
                                run_fci=parameters.psi4.run_fci,
                                verbose=parameters.psi4.verbose,
                                tolerate_error=parameters.psi4.tolerate_error,
                                delete_input=parameters.psi4.delete_input,
                                delete_output=parameters.psi4.delete_output,
                                memory=parameters.psi4.memory)

        molecule.save()
        print("file was ", molecule.filename)
        return molecule

    def parse_ccsd_amplitudes(self, filename=None):
        if filename is None:
            filename = self.parameters.filename

        from os import path, access, R_OK
        file_exists = path.isfile("./"+filename) and access("./"+filename, R_OK)

        # make sure the molecule is there, i.e. psi4 has been run
        # and that the output was kept, as well as CCSD was actually computed
        if not file_exists or (self.molecule is None or self.parameters.psi4.run_ccsd == False or self.parameters.psi4.delete_output):
            self.print("Recomputing PSI4", level=OutputLevel.STANDARD)
            self.parameters.filename = filename.strip(".out")
            self.parameters.psi4.run_ccsd = True
            self.parameters.psi4.delete_output = False
            self.molecule = self.make_molecule(self.parameters)

        # adapting to the openfermion parser
        if ".out" not in filename:
            filename += ".out"

        singles, doubles = parse_psi4_ccsd_amplitudes(number_orbitals=self.n_orbitals() * 2,
                                                      n_alpha_electrons=self.n_electrons() // 2,
                                                      n_beta_electrons=self.n_electrons() // 2,
                                                      psi_filename=filename)

        return ManyBodyAmplitudes(one_body=singles, two_body=doubles)

    def parse_mp2_amplitudes(self):
        raise NotImplementedError("not implemented yet")