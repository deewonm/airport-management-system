# Exam number: 125378591

from datetime import datetime, timedelta


class AirportError(Exception):
    """Raised when an airport rule is broken."""


class Employee:
    """Airport staff, e.g. a ramp agent or team leader for this assignment.

    Attributes:
        employee_id: The unique ID of the employee.
        role: The job role of the employee.
        available: Whether the employee can be given a task.
    """

    def __init__(self, name, employee_id, role, available=True):
        """Initializes an Employee.

        Args:
            name: The employee's name.
            employee_id: The employee's unique ID.
            role: The employee's job role.
            available: Whether the employee can currently be given a task.

        Raises:
            ValueError: If name or employee_id is empty.
            TypeError: If available is not True or False.
        """

        if not name or not employee_id:
            raise ValueError("Name and employee ID must not be empty")
        self._name = name
        self._employee_id = employee_id
        self._role = role
        self.available = available

    def __str__(self):
        """Returns a readable summary of the employee."""

        return (f"Employee: {self._name}, {self._employee_id}, {self._role}, "
               f"{self._available}")

    @property
    def employee_id(self):
        """str: The unique ID of the employee."""

        return self._employee_id

    @property
    def role(self):
        """str: The job role of the employee."""

        return self._role

    @property
    def available(self):
        """bool: Whether the employee can be given a task.

        Raises:
            TypeError: If set to a value that is not True or False.
        """

        return self._available

    @available.setter
    def available(self, value):
        if not isinstance(value, bool):
            raise TypeError("Availability must be True or False")
        self._available = value


class RampAgent(Employee):
    """Crew member that carries out tasks on the ramp.

    Attributes:
        employee_id: The unique ID of the agent.
        role: The job role of the agent, always "Ramp Agent".
        available: Whether the agent can be given a task.
    """

    def __init__(self, name, employee_id, available=True):
        """Initializes a RampAgent with no task assigned.

        Args:
            name: The agent's name.
            employee_id: The agent's unique ID.
            available: Whether the agent can currently be given a task.

        Raises:
            ValueError: If name or employee_id is empty.
            TypeError: If available is not True or False.
        """

        super().__init__(name, employee_id, "Ramp Agent", available)
        self._task = None

    def get_task(self):
        """Returns the agent's current task, or None if there is none."""

        return self._task

    def assign_task(self, task):
        """Gives the agent a task and marks them unavailable.

        Args:
            task: A description of the task to carry out.

        Returns:
            True if the task was assigned.

        Raises:
            AirportError: If the agent is not available.
        """

        if not self.available:
            raise AirportError("Employee not available!")
        self._task = task
        self.available = False
        return True

    def complete_task(self):
        """Clears the agent's current task and marks them available.

        Returns:
            True if the task was completed.

        Raises:
            AirportError: If the agent has no task assigned.
        """

        if self._task is None:
            raise AirportError("Ramp agent has no task assigned currently!")
        self._task = None
        self.available = True
        return True


class TeamLeader(Employee):
    """Head of the flight team who approves crews.

    Attributes:
        employee_id: The unique ID of the team leader.
        role: The job role of the team leader, always "Team Leader".
        available: Whether the team leader can be given a task.
    """

    def __init__(self, name, employee_id, available=True):
        """Initializes a TeamLeader.

        Args:
            name: The team leader's name.
            employee_id: The team leader's unique ID.
            available: Whether the team leader is currently available.

        Raises:
            ValueError: If name or employee_id is empty.
            TypeError: If available is not True or False.
        """

        super().__init__(name, employee_id, "Team Leader", available)

    def assign_task(self, ramp_agent, task):
        """Assigns a task to a ramp agent.

        Args:
            ramp_agent: The RampAgent to give the task to.
            task: A description of the task to carry out.

        Returns:
            True if the task was assigned.

        Raises:
            AirportError: If the ramp agent is not available.
        """

        return ramp_agent.assign_task(task)

    def approve_crew(self, crew):
        """Approves a crew for a flight.

        Args:
            crew: The GroundCrew to approve.

        Returns:
            True if the crew was approved.

        Raises:
            AirportError: If the crew does not meet the requirements or this
                team leader is not a member of it.
        """

        if not crew.meets_requirements():
            raise AirportError("Crew does not meet flight requirements!!!")
        if self not in crew.get_members():
            raise AirportError("Warning: flight requires a team leader!")
        return True


class GroundCrew:
    """A crew of 4 employees including 1 team leader."""

    def __init__(self, crew_num):
        """Initializes an empty GroundCrew.

        Args:
            crew_num: The number identifying this crew.
        """

        self._crew_num = crew_num
        self._members = []

    def add_member(self, employee):
        """Adds an employee to the crew.

        Args:
            employee: The Employee to add.

        Raises:
            AirportError: If the crew is full or the employee is already in
                the crew.
        """

        if len(self._members) >= 4:
            raise AirportError("Crew already has 4 members!")
        if employee in self._members:
            raise AirportError("Employee already in Crew!")

        self._members.append(employee)

    def get_members(self):
        """Returns the crew members as a tuple.

        A tuple is returned so that outside changes cannot affect the crew.
        """

        return tuple(self._members)

    def remove_members(self, employee):
        """Removes an employee from the crew.

        Args:
            employee: The Employee to remove.

        Raises:
            AirportError: If the employee is not in the crew.
        """

        if employee not in self._members:
            raise AirportError("Employee not in team!")
        self._members.remove(employee)

    def meets_requirements(self):
        """Checks whether the crew is valid for a flight.

        Returns:
            True if the crew has 4 members including exactly one team leader,
            otherwise False.
        """

        if len(self._members) != 4:
            return False
        team_lead = 0
        for employee in self._members:
            if type(employee) is TeamLeader:
                team_lead += 1
        return team_lead == 1


class Flight:
    """A departure that can have 1 approved crew.

    Attributes:
        flight_code: The unique code of the flight.
        dest: The destination of the flight.
        etd: The estimated time of departure as a datetime.
        crew: The GroundCrew assigned to the flight, or None.
        cancelled: Whether the flight has been cancelled.
    """

    def __init__(self, flight_code, dest, etd):
        """Initializes a Flight with no crew that is not cancelled.

        Args:
            flight_code: The unique code of the flight, e.g. "FR9006".
            dest: The destination of the flight.
            etd: The estimated time of departure.

        Raises:
            ValueError: If flight_code or dest is empty.
            TypeError: If etd is not a datetime.
        """

        if not flight_code or not dest:
            raise ValueError("Flight code and destination cannot be empty")
        if not isinstance(etd, datetime):
            raise TypeError("ETD must be a datetime")
        self._flight_code = flight_code
        self._dest = dest
        self._etd = etd
        self._crew = None
        self._cancelled = False

    @property
    def flight_code(self):
        """str: The unique code of the flight."""

        return self._flight_code

    @property
    def dest(self):
        """str: The destination of the flight."""

        return self._dest

    @property
    def etd(self):
        """datetime: The estimated time of departure."""

        return self._etd

    @property
    def crew(self):
        """GroundCrew: The crew assigned to the flight, or None."""

        return self._crew

    @property
    def cancelled(self):
        """bool: Whether the flight has been cancelled."""

        return self._cancelled

    def assign_approved_crew(self, crew):
        """Assigns a crew to the flight.

        Args:
            crew: The GroundCrew to assign.

        Returns:
            True if the crew was assigned.

        Raises:
            AirportError: If the flight already has a crew or the crew does
                not meet the requirements.
        """

        if self._crew is not None:
            raise AirportError("Flight has an active team!")

        if not crew.meets_requirements():
            raise AirportError("Crew does not meet requirements")
        self._crew = crew
        return True

    def remove_crew(self):
        """Removes the crew from the flight.

        Raises:
            AirportError: If the flight has no crew.
        """

        if self._crew is None:
            raise AirportError("Flight has no crew to remove")
        self._crew = None

    def delay_flight(self, minutes, hours):
        """Moves the departure time back by the given delay.

        Args:
            minutes: The number of minutes to delay by.
            hours: The number of hours to delay by.

        Raises:
            ValueError: If minutes or hours is negative.
        """

        if minutes < 0 or hours < 0:
            raise ValueError("Delay cannot be negative")
        self._etd += timedelta(minutes=minutes, hours=hours)

    def flight_cancelled(self):
        """Marks the flight as cancelled and removes its crew."""

        self._cancelled = True
        self._crew = None


class Airport:
    """An airport and the employees and flights it manages."""

    def __init__(self, name, iata_code):
        """Initializes an Airport with no employees or flights.

        Args:
            name: The name of the airport.
            iata_code: The airport's three-letter IATA code.
        """

        self._name = name
        self._iata_code = iata_code
        self._employees = []
        self._flights = []

    def add_employee(self, employee):
        """Adds an employee to the airport.

        Args:
            employee: The Employee to add.

        Raises:
            AirportError: If an employee with the same ID already exists.
        """

        for existing_employee in self._employees:
            if existing_employee.employee_id == employee.employee_id:
                raise AirportError("Staff ID already exists")
        self._employees.append(employee)

    def add_flight(self, flight):
        """Adds a flight to the airport.

        Args:
            flight: The Flight to add.

        Raises:
            AirportError: If a flight with the same code already exists.
        """

        for existing_flight in self._flights:
            if existing_flight.flight_code == flight.flight_code:
                raise AirportError("Cannot duplicate Flights")
        self._flights.append(flight)

    def find_flight(self, flight_code):
        """Finds a flight by its code.

        Args:
            flight_code: The code of the flight to look for.

        Returns:
            The Flight with this code, or None if it is not found.
        """

        for flight in self._flights:
            if flight.flight_code == flight_code:
                return flight
        return None


def test():
    airport = Airport("Cork Airport", "ORK")

    team_leader = TeamLeader("Jonathan", "808123")
    agent1 = RampAgent("Peter", "807544")
    agent2 = RampAgent("jan", "807545")
    agent3 = RampAgent("Peter", "807546")

    airport.add_employee(team_leader)
    airport.add_employee(agent1)
    airport.add_employee(agent2)
    airport.add_employee(agent3)

    crew = GroundCrew(1)

    crew.add_member(team_leader)
    crew.add_member(agent1)
    crew.add_member(agent2)
    crew.add_member(agent3)

    print(crew.meets_requirements())
    print(team_leader.approve_crew(crew))

    departure = datetime(2026, 10, 11, 14, 30)
    flight = Flight("FR9006", "STN", departure)
    airport.add_flight(flight)
    print(flight.assign_approved_crew(crew))
    flight.delay_flight(hours=2, minutes=38)
    print(flight.etd)

    print("Error handling sample test:)")

    # Crew is already full
    try:
        crew.add_member(RampAgent("Daniel", "807547"))
    except AirportError as error:
        print(f"Error: {error}")

    # Trying to assign task when agent is busy
    agent1.assign_task("Load bags")
    try:
        agent1.assign_task("Refuelling Diesel tugs")
    except AirportError as error:
        print(f"Error: {error}")

    # Empty name
    try:
        RampAgent("", "111115")
    except ValueError as error:
        print(f"Error: {error}")

    # Negative delay
    try:
        flight.delay_flight(minutes=-5, hours=0)
    except ValueError as error:
        print(f"Error: {error}")

    # ETD must be a datetime, not string
    try:
        Flight("EI100", "LHR", "tomorrow")
    except TypeError as error:
        print(f"Error: {error}")

    # Only accepts True or False
    try:
        agent1.available = "yes"
    except TypeError as error:
        print(f"Error: {error}")


# Only run the sample test when this file is run directly,
# not when Flask imports it.
if __name__ == "__main__":
    test()