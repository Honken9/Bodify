export type Me = {
  id: string;
  email: string;
  display_name: string | null;
  is_admin: boolean;
};

export type Exercise = {
  id: string;
  name: string;
  muscle_groups: string[];
  equipment: string[];
  is_global: boolean;
};

export type ProgramDayExercise = {
  id: string;
  exercise: Exercise;
  position: number;
  target_sets: number;
  target_reps: string;
  rest_seconds: number;
  notes: string | null;
};

export type ProgramDay = {
  id: string;
  name: string;
  position: number;
  exercises: ProgramDayExercise[];
};

export type Program = {
  id: string;
  name: string;
  description: string | null;
  level: "beginner" | "intermediate" | "advanced";
  days_per_week: number | null;
  is_global: boolean;
  days: ProgramDay[];
};

export type UserProgram = {
  id: string;
  program: Program;
  started_at: string;
  next_day_position: number;
  is_active: boolean;
};

export type WorkoutSet = {
  id: string;
  exercise_id: string;
  set_number: number;
  weight_kg: number | null;
  reps: number;
  rpe: number | null;
  is_warmup: boolean;
};

export type PreviousSets = {
  performed_at: string;
  sets: WorkoutSet[];
};

export type SessionExercisePlan = {
  exercise: Exercise;
  target_sets: number | null;
  target_reps: string | null;
  rest_seconds: number | null;
  notes: string | null;
  previous: PreviousSets | null;
};

export type SessionDetail = {
  id: string;
  started_at: string;
  finished_at: string | null;
  notes: string | null;
  day_name: string | null;
  program_name: string | null;
  plan: SessionExercisePlan[];
  sets: WorkoutSet[];
};

export type SessionSummary = {
  id: string;
  started_at: string;
  finished_at: string | null;
  notes: string | null;
  day_name: string | null;
  program_name: string | null;
  set_count: number;
  total_volume_kg: number;
};

export const LEVEL_LABELS: Record<Program["level"], string> = {
  beginner: "Nybörjare",
  intermediate: "Medel",
  advanced: "Avancerad",
};
