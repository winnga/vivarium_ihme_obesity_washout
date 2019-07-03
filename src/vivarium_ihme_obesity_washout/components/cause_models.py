
class CKD_SI:

    def __init__(self):
        self.cause = 'chronic_kidney_disease'
        self.subcauses = ['chronic_kidney_disease_due_to_hypertension',
            'chronic_kidney_disease_due_to_glomerulonephritis',
            'chronic_kidney_disease_due_to_other_and_unspecified_causes',
            'chronic_kidney_disease_due_to_diabetes_mellitus_type_1',
            'chronic_kidney_disease_due_to_diabetes_mellitus_type_2']

    @property
    def name(self):
        return self.cause

    def setup(self, builder):
        disease_model_data_functions = {}

        healthy = SusceptibleState(self.cause, get_data_functions={'incidence': self.get_incidence})
        infected = ExcessMortalityState(self.cause, get_data_functions={
            'prevalence': self.get_prevalence,
            'excess_mortality': self.get_excess_mortality,
            'disability_weight': self.get_disability_weight}
            )

        healthy.allow_self_transitions()
        healthy.add_transition(infected, source_data_type='rate')
        infected.allow_self_transitions()

        builder.components.add_components([DiseaseModel(self.cause, states=[healthy, infected],
                                                        get_data_functions={'csmr': self.get_cause_specific_mortality})])

    def get_prevalence(self, _, builder):
        for cause in self.subcauses:
            builder.data.load(f'cause.{cause}.prevalence')

    def get_incidence(self, _, builder):
        for cause in self.subcauses:
            builder.data.load(f'cause.{cause}.incidence')

    def get_excess_mortality(self, _, builder):
        for cause in self.subcauses:
            builder.data.load(f'cause.{cause}.excess_mortality')

    def get_disability_weight(self, _, builder):
        for cause in self.subcauses:
            builder.data.load(f'cause.{cause}.disability_weight')

    def get_cause_specific_mortality(self, _, builder):
        for cause in self.subcauses:
            builder.data.load(f'cause.{cause}.cause_specific_mortality')

    def __repr__(self):
        return 'CKD_SI'


class DiabetesSIS:

    def __init__(self):
        self.cause = 'diabetes_mellitus_type_2'

    @property
    def name(self):
        return f'SIS.{self.cause}'

    def setup(self, builder):
        healthy = SusceptibleState(self.cause)
        infected = ExcessMortalityState(self.cause)

        healthy.allow_self_transitions()
        healthy.add_transition(infected, source_data_type='rate')
        infected.allow_self_transitions()
        infected.add_transition(healthy, source_data_type='rate', get_data_functions={
            'remission_rate': lambda _, builder: builder.data.load('cause.diabetes_mellitus.remission')
        })

        builder.components.add_components([DiseaseModel(self.cause, states=[healthy, infected])])

    def __repr__(self):
        return 'DiabetesSIS'


