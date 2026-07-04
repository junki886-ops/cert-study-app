import streamlit_app


def test_learning_landing_routes_are_registered():
    routes = streamlit_app.learning_landing_routes()

    assert routes["개념공부"] == streamlit_app.render_concept_mode_home
    assert routes["개념 공부"] == streamlit_app.render_concept_mode_home
    assert routes["실습"] == streamlit_app.render_practice_mode_home
    assert routes["시험준비"] == streamlit_app.render_exam_prep_home
    assert routes["시험 준비"] == streamlit_app.render_exam_prep_home
