

class ActivityNameManager:
    activity_name_restore_map = {}

    @classmethod
    def fix_activity_name(cls, activity):
        original_activity_name = activity
        activity = activity.split('.')[-1]
        # if activity.startswith('.'):
        #     activity = f'{agent_config.package_name}.{activity[1:]}'
        if activity.endswith('}'):
            activity = activity[:-1]
        if activity.endswith('Activity'):
            activity = activity.removesuffix('Activity')
        elif activity.endswith('activity'):
            activity = activity.removesuffix('activity')

        if activity not in cls.activity_name_restore_map:
            cls.activity_name_restore_map[activity] = original_activity_name

        return activity