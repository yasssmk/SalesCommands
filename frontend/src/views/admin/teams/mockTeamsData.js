// frontend/src/views/admin/teams/mockTeamsData.js

/**
 * ⚠️ TEMPORARY MOCK DATA - TODO: Replace with API
 */

export const mockTeams = [
  {
    id: '1',
    name: 'Sales Organization',
    description: 'Main sales organization',
    manager: {
      id: 'u1',
      first_name: 'John',
      last_name: 'Doe',
      email: 'john.doe@company.com'
    },
    parent: null,
    member_count: 25,
    created_at: '2024-01-15T10:00:00Z',
    children: [
      {
        id: '2',
        name: 'Sales Team North',
        description: 'North region sales team',
        manager: {
          id: 'u2',
          first_name: 'Jane',
          last_name: 'Smith',
          email: 'jane.smith@company.com'
        },
        parent: '1',
        member_count: 12,
        created_at: '2024-02-01T10:00:00Z',
        children: [
          {
            id: '4',
            name: 'Sales Sub-Team A',
            description: 'Enterprise clients',
            manager: null,
            parent: '2',
            member_count: 5,
            created_at: '2024-03-01T10:00:00Z',
            children: []
          },
          {
            id: '5',
            name: 'Sales Sub-Team B',
            description: 'SMB clients',
            manager: {
              id: 'u5',
              first_name: 'Mike',
              last_name: 'Brown',
              email: 'mike.brown@company.com'
            },
            parent: '2',
            member_count: 7,
            created_at: '2024-03-15T10:00:00Z',
            children: []
          }
        ]
      },
      {
        id: '3',
        name: 'Sales Team South',
        description: 'South region sales team',
        manager: {
          id: 'u3',
          first_name: 'Bob',
          last_name: 'Johnson',
          email: 'bob.johnson@company.com'
        },
        parent: '1',
        member_count: 8,
        created_at: '2024-02-10T10:00:00Z',
        children: []
      }
    ]
  },
  {
    id: '6',
    name: 'Marketing Organization',
    description: 'Marketing and communications',
    manager: {
      id: 'u4',
      first_name: 'Alice',
      last_name: 'Williams',
      email: 'alice.williams@company.com'
    },
    parent: null,
    member_count: 18,
    created_at: '2024-01-20T10:00:00Z',
    children: [
      {
        id: '7',
        name: 'Digital Marketing',
        description: 'Online marketing',
        manager: {
          id: 'u6',
          first_name: 'Sarah',
          last_name: 'Davis',
          email: 'sarah.davis@company.com'
        },
        parent: '6',
        member_count: 10,
        created_at: '2024-02-15T10:00:00Z',
        children: []
      },
      {
        id: '8',
        name: 'Content Marketing',
        description: 'Content creation',
        manager: null,
        parent: '6',
        member_count: 8,
        created_at: '2024-02-20T10:00:00Z',
        children: []
      }
    ]
  },
  {
    id: '9',
    name: 'Engineering',
    description: 'Product development',
    manager: {
      id: 'u7',
      first_name: 'David',
      last_name: 'Wilson',
      email: 'david.wilson@company.com'
    },
    parent: null,
    member_count: 45,
    created_at: '2024-01-10T10:00:00Z',
    children: [
      {
        id: '10',
        name: 'Frontend Team',
        description: 'UI/UX development',
        manager: {
          id: 'u8',
          first_name: 'Emma',
          last_name: 'Taylor',
          email: 'emma.taylor@company.com'
        },
        parent: '9',
        member_count: 15,
        created_at: '2024-02-05T10:00:00Z',
        children: []
      },
      {
        id: '11',
        name: 'Backend Team',
        description: 'API and infrastructure',
        manager: {
          id: 'u9',
          first_name: 'Chris',
          last_name: 'Martinez',
          email: 'chris.martinez@company.com'
        },
        parent: '9',
        member_count: 20,
        created_at: '2024-02-08T10:00:00Z',
        children: []
      }
    ]
  }
];

export function findTeamById(teams, id) {
  for (const team of teams) {
    if (team.id === id) return team;
    if (team.children) {
      const found = findTeamById(team.children, id);
      if (found) return found;
    }
  }
  return null;
}

export function flattenTeams(teams) {
  const result = [];
  function traverse(team) {
    result.push(team);
    if (team.children) {
      team.children.forEach(traverse);
    }
  }
  teams.forEach(traverse);
  return result;
}